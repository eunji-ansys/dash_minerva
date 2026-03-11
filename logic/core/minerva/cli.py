import os
import json
import shlex
import logging
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal, Optional, Union

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger("MinervaCLI")

# -------------------------------------------------------------------
# Types
# -------------------------------------------------------------------
AuthMode = Literal["Explicit", "Impersonate", "Refresh_Token", "Windows"]
InteractiveMode = Literal["None", "Console", "Graphical"]
OverwriteMode = Literal["Error", "Overwrite", "Append", "Ignore", "Snapshot"]
SelectMode = Literal["SaveFile", "SelectFile", "SelectFolder", "SelectFileFolder"]


# -------------------------------------------------------------------
# Exception
# -------------------------------------------------------------------
class MinervaCliError(RuntimeError):
    """Raised when Minerva CLI execution fails, with debug metadata."""

    def __init__(
        self,
        message: str,
        *,
        returncode: int,
        stdout: str,
        stderr: str,
        command: List[str],
    ):
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.command = command

    def __str__(self) -> str:
        cmd = " ".join(shlex.quote(str(x)) for x in self.command)
        return (
            f"{super().__str__()}\n"
            f"Return Code: {self.returncode}\n"
            f"Command: {cmd}\n"
            f"STDOUT: {self.stdout.strip()}\n"
            f"STDERR: {self.stderr.strip()}"
        )


# -------------------------------------------------------------------
# Small helpers
# -------------------------------------------------------------------
def _listify(value: Union[str, Iterable[str], None]) -> List[str]:
    """Normalize string or iterable into a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _add_many(flag: str, values: Union[str, Iterable[str], None]) -> List[str]:
    """Add repeated flags: ['--remote', a, '--remote', b, ...]."""
    out: List[str] = []
    for v in _listify(values):
        out += [flag, v]
    return out


def _mask_env(env: Dict[str, str]) -> Dict[str, str]:
    """Mask sensitive environment values for logging."""
    masked = dict(env)
    for k in list(masked.keys()):
        if any(x in k.upper() for x in ("PASSWORD", "TOKEN", "SECRET", "KEY", "CREDENTIAL", "BEARER")):
            masked[k] = "***"
    return masked


# -------------------------------------------------------------------
# Auth model
# -------------------------------------------------------------------
@dataclass(frozen=True)
class CLIAuthOptions:
    """Authentication configuration for Minerva CLI execution."""
    mode: AuthMode
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    certconfig: Optional[str] = None


# -------------------------------------------------------------------
# Client (3-layer args: runtime / workspace / server)
# -------------------------------------------------------------------
class MinervaCLIClient:
    """
    Minerva CLI wrapper with:
    - 3-layer argument model:
        (1) runtime args: interactive/output/ui-theme
        (2) workspace args: local working directory
        (3) server args: url + auth flags (+ env secrets)
    - Reconfigurable authentication via set_auth()
    - Execution env built once per auth configuration (self._exec_env)
    """

    def __init__(
        self,
        *,
        base_url: str,
        database: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_mode: AuthMode = "Explicit",
        token: Optional[str] = None,
        certconfig: Optional[str] = None,
        cli_exe_path: Optional[str] = None,
        name: Optional[str] = None,
        interactive: InteractiveMode = "None",
        output: str = "stream://stdout",
        ui_theme: Optional[str] = None,
        default_timeout: Optional[float] = None,
    ):
        if not base_url:
            raise ValueError("base_url is required.")
        if not database:
            raise ValueError("database is required.")

        self.base_url = base_url
        self.database = database
        self.default_timeout = default_timeout

        # Logging context
        if name:
            self.name = name
        else:
            short = base_url.replace("https://", "").replace("http://", "").rstrip("/")
            self.name = f"{short}|{database}"
        self._pfx = f"[{self.name}] "

        # CLI executable path
        self.exe = cli_exe_path or os.environ.get("ANS_MINERVA_CLI")
        if not self.exe or not os.path.exists(self.exe):
            raise FileNotFoundError(f"{self._pfx}CLI executable not found: {self.exe}")

        # (1) Runtime args (built once)
        self._runtime_args = self._build_runtime_args(
            interactive=interactive,
            output=output,
            ui_theme=ui_theme,
        )

        # (3) Server args base (built once; auth args are set via set_auth)
        self._server_base_args = self._build_server_base_args(base_url=self.base_url)

        # Initialize authentication through the public method
        self.set_auth(
            mode=auth_mode,
            username=username,
            password=password,
            token=token,
            certconfig=certconfig,
        )

    # -------------------------------------------------------------------
    # Layer (1): runtime args
    # -------------------------------------------------------------------
    def _build_runtime_args(
        self,
        *,
        interactive: InteractiveMode,
        output: str,
        ui_theme: Optional[str],
    ) -> List[str]:
        """Build runtime execution args (no server/workspace semantics)."""
        args: List[str] = ["--interactive", interactive, "--output", output]
        if ui_theme:
            args += ["--ui-theme", ui_theme]
        return args

    # -------------------------------------------------------------------
    # Layer (2): workspace args
    # -------------------------------------------------------------------
    def _build_workspace_args(self, *, local: Optional[str]) -> List[str]:
        """Build workspace args (local working directory / session context)."""
        if not local:
            return []
        return ["--local", local]

    # -------------------------------------------------------------------
    # Layer (3): server args (url + auth)
    # -------------------------------------------------------------------
    def _build_server_base_args(self, *, base_url: str) -> List[str]:
        """Build server base args (url only)."""
        return ["--url", base_url]

    def _validate_auth(self, auth: CLIAuthOptions) -> None:
        """Validate authentication configuration."""
        if auth.mode == "Explicit":
            if not auth.username or not auth.password:
                raise ValueError(f"{self._pfx}Explicit mode requires username and password.")
            if auth.token or auth.certconfig:
                raise ValueError(f"{self._pfx}Explicit mode must not use token or certconfig.")

        elif auth.mode == "Refresh_Token":
            if not auth.token:
                raise ValueError(f"{self._pfx}Refresh_Token mode requires token.")
            if auth.password or auth.certconfig:
                raise ValueError(f"{self._pfx}Refresh_Token mode must not use password or certconfig.")

        elif auth.mode == "Impersonate":
            if not auth.certconfig:
                raise ValueError(f"{self._pfx}Impersonate mode requires certconfig path.")
            if auth.password or auth.token:
                raise ValueError(f"{self._pfx}Impersonate mode must not use password or token.")

        elif auth.mode == "Windows":
            if auth.password or auth.token or auth.certconfig:
                raise ValueError(f"{self._pfx}Windows mode must not use password, token, or certconfig.")

        else:
            raise ValueError(f"{self._pfx}Unknown auth mode: {auth.mode!r}")

    def _build_auth_env(self, auth: CLIAuthOptions) -> Dict[str, str]:
        """Build authentication-related environment variables (secrets)."""
        env: Dict[str, str] = {}
        if auth.mode == "Explicit":
            env["ANS_MINERVA_AUTH__PASSWORD"] = auth.password  # type: ignore[assignment]
        elif auth.mode == "Refresh_Token":
            env["ANS_MINERVA_AUTH__TOKEN"] = auth.token  # type: ignore[assignment]
        return env

    def _build_auth_args(self, auth: CLIAuthOptions) -> List[str]:
        """Build authentication-related CLI flags (non-secrets)."""
        args: List[str] = ["--auth:database", self.database]
        if auth.username:
            args += ["--auth:user", auth.username]
        args += ["--auth:mode", auth.mode]
        if auth.mode == "Impersonate":
            args += ["--auth:certconfig", auth.certconfig]  # validated non-null
        return args

    # -------------------------------------------------------------------
    # Public: update auth
    # -------------------------------------------------------------------
    def set_auth(
        self,
        *,
        mode: AuthMode,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        certconfig: Optional[str] = None,
    ) -> None:
        """
        Update authentication configuration.
        Rebuilds auth args and execution environment.
        """
        auth = CLIAuthOptions(
            mode=mode,
            username=username,
            password=password,
            token=token,
            certconfig=certconfig,
        )
        self._validate_auth(auth)

        self._auth = auth
        self._auth_args = self._build_auth_args(auth)

        # Build execution environment once per auth configuration
        auth_env = self._build_auth_env(auth)
        self._exec_env = os.environ.copy()
        self._exec_env.update(auth_env)

        logger.debug(f"{self._pfx}[AUTH] Updated auth mode={mode}, user={username!r}")

    # -------------------------------------------------------------------
    # Core execution
    # -------------------------------------------------------------------
    def _run(
        self,
        command: str,
        args: List[str],
        *,
        parse_json: bool = False,
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
    ) -> Union[str, Any]:
        full_cmd = [self.exe, command] + args
        cmd_str = " ".join(shlex.quote(str(x)) for x in full_cmd)

        eff_timeout = self.default_timeout if timeout is None else timeout

        logger.debug("=" * 70)
        logger.debug(f"{self._pfx}[EXECUTE] {cmd_str}")
        logger.debug(f"{self._pfx}[AUTH_ENV] {_mask_env(self._build_auth_env(self._auth))}")
        logger.debug("=" * 70)

        try:
            cp = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self._exec_env,
                timeout=eff_timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired as e:
            raise MinervaCliError(
                f"{self._pfx}CLI timed out: {command}",
                returncode=-1,
                stdout=(e.stdout or ""),
                stderr=(e.stderr or ""),
                command=full_cmd,
            ) from e

        if cp.returncode != 0:
            raise MinervaCliError(
                f"{self._pfx}CLI failed: {command}",
                returncode=cp.returncode,
                stdout=cp.stdout or "",
                stderr=cp.stderr or "",
                command=full_cmd,
            )

        out = cp.stdout or ""
        if parse_json:
            try:
                return json.loads(out)
            except json.JSONDecodeError as e:
                raise MinervaCliError(
                    f"{self._pfx}Invalid JSON output: {command}",
                    returncode=cp.returncode,
                    stdout=out,
                    stderr=cp.stderr or "",
                    command=full_cmd,
                ) from e

        return out

    # -------------------------------------------------------------------
    # Command arg composition
    # -------------------------------------------------------------------
    def _server_command_args(self, *, local: Optional[str], include_auth: bool = True) -> List[str]:
        """Compose args for server-backed commands."""
        args = self._server_base_args + (self._auth_args if include_auth else []) + self._runtime_args
        args += self._build_workspace_args(local=local)
        return args

    def _local_command_args(self, *, local: Optional[str]) -> List[str]:
        """Compose args for local-context commands."""
        args = self._runtime_args + self._build_workspace_args(local=local)
        return args

    # -------------------------------------------------------------------
    # Server-backed commands
    # -------------------------------------------------------------------
    def sign_in(
        self,
        *,
        force: bool = False,
        local: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Sign in to Minerva."""
        args = self._server_command_args(local=local, include_auth=True)
        if force:
            args += ["--force"]
        return self._run("sign-in", args, timeout=timeout, parse_json=parse_json)

    def sign_out(
        self,
        *,
        local: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Sign out from Minerva."""
        # Sign-out typically does not require auth flags; keep it conservative.
        args = self._server_command_args(local=local, include_auth=False)
        return self._run("sign-out", args, timeout=timeout, parse_json=parse_json)

    def claim(
        self,
        remote: Union[str, Iterable[str]],
        *,
        globs: Union[str, Iterable[str], None] = None,
        local: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Claim one or more remote items for exclusive editing."""
        args = self._server_command_args(local=local, include_auth=True)
        args += _add_many("--glob", globs)
        args += _add_many("--remote", remote)
        return self._run("claim", args, timeout=timeout, parse_json=parse_json)

    def unclaim(
        self,
        remote: Union[str, Iterable[str]],
        *,
        globs: Union[str, Iterable[str], None] = None,
        local: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Unclaim one or more remote items."""
        args = self._server_command_args(local=local, include_auth=True)
        args += _add_many("--glob", globs)
        args += _add_many("--remote", remote)
        return self._run("unclaim", args, timeout=timeout, parse_json=parse_json)

    def download(
        self,
        remote: Union[str, Iterable[str]],
        *,
        local: Optional[str] = None,
        overwrite: OverwriteMode = "Overwrite",
        no_session: bool = False,
        content: bool = False,
        dependencies: Optional[bool] = None,
        filter: Optional[str] = None,
        path: Optional[str] = None,
        remote_start: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Download remote items to a local directory."""
        args = self._server_command_args(local=local, include_auth=True)

        args += ["--overwrite", overwrite]
        if no_session:
            args += ["--no-session"]
        if content:
            args += ["--content"]
        if dependencies is not None:
            args += ["--dependencies", "True" if dependencies else "False"]
        if filter:
            args += ["--filter", filter]
        if path:
            args += ["--path", path]
        if remote_start:
            args += ["--remote-start", remote_start]

        args += _add_many("--remote", remote)
        return self._run("download", args, timeout=timeout, parse_json=parse_json)

    def fetch_status(
        self,
        *,
        glob: Union[str, Iterable[str], None] = None,
        local: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Query latest information for local files."""
        args = self._server_command_args(local=local, include_auth=True)
        args += _add_many("--glob", glob)
        return self._run("fetch-status", args, timeout=timeout, parse_json=parse_json)

    def select_items(
        self,
        *,
        mode: SelectMode,
        filter: Optional[str] = None,
        dependencies: Optional[bool] = None,
        multi_select: Optional[bool] = None,
        remote_start: Optional[str] = None,
        remote: Union[str, Iterable[str], None] = None,
        local: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Select items in Minerva and output a JSON description."""
        args = self._server_command_args(local=local, include_auth=True)

        args += ["--mode", mode]
        if dependencies is not None:
            args += ["--dependencies", "True" if dependencies else "False"]
        if filter:
            args += ["--filter", filter]
        if multi_select is not None:
            args += ["--multiSelect", "True" if multi_select else "False"]
        if remote_start:
            args += ["--remote-start", remote_start]
        args += _add_many("--remote", remote)

        return self._run("select-items", args, timeout=timeout, parse_json=parse_json)

    def upload(
        self,
        remote: str,
        *,
        local: Optional[str] = None,
        glob: Union[str, Iterable[str], None] = None,
        overwrite: OverwriteMode = "Overwrite",
        no_session: bool = False,
        close_session: bool = False,
        override_minervaignore: Union[str, Iterable[str], None] = None,
        remote_start: Optional[str] = None,
        version_folders: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Upload files from a local directory to Minerva."""
        args = self._server_command_args(local=local, include_auth=True)

        args += ["--remote", remote, "--overwrite", overwrite]
        if no_session:
            args += ["--no-session"]
        if close_session:
            args += ["--close-session"]

        args += _add_many("--glob", glob)
        args += _add_many("--override-minervaignore", override_minervaignore)

        if remote_start:
            args += ["--remote-start", remote_start]
        if version_folders:
            args += ["--version-folders", version_folders]

        return self._run("upload", args, timeout=timeout, parse_json=parse_json)

    # -------------------------------------------------------------------
    # Local-context commands
    # -------------------------------------------------------------------
    def get_local(
        self,
        path: str,
        *,
        local: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Return working directory information for a local file/folder."""
        args = ["--path", path] + self._local_command_args(local=local)
        return self._run("get-local", args, timeout=timeout, parse_json=parse_json)

    def get_status(
        self,
        *,
        local: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Show which files have been staged for upload."""
        args = self._local_command_args(local=local)
        return self._run("get-status", args, timeout=timeout, parse_json=parse_json)

    def stage(
        self,
        globs: Union[str, Iterable[str]],
        *,
        local: Optional[str] = None,
        override_minervaignore: Union[str, Iterable[str], None] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Stage files for upload based on glob patterns."""
        args = _add_many("--glob", globs)
        args += _add_many("--override-minervaignore", override_minervaignore)
        args += self._local_command_args(local=local)
        return self._run("stage", args, timeout=timeout, parse_json=parse_json)

    def unstage(
        self,
        globs: Union[str, Iterable[str]],
        *,
        local: Optional[str] = None,
        timeout: Optional[float] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Remove files from the staging list."""
        args = _add_many("--glob", globs)
        args += self._local_command_args(local=local)
        return self._run("unstage", args, timeout=timeout, parse_json=parse_json)


# -------------------------------------------------------------------
# Entry Point
# -------------------------------------------------------------------
if __name__ == "__main__":

    # Optional: python-dotenv (pip install python-dotenv)
    try:
        from dotenv import load_dotenv
    except Exception:
        load_dotenv = None

    if load_dotenv:
        load_dotenv()

    # ---------------------------------------------------------
    # 1️⃣ 기본 설정 (환경 변수 사용 권장)
    # ---------------------------------------------------------
    base_url = os.getenv("MINERVA_BASE_URL")
    database = os.getenv("MINERVA_DATABASE")
    username = os.getenv("MINERVA_USERNAME")
    password = os.getenv("MINERVA_PASSWORD")
    local_path = os.getenv("TEMP_DOWNLOAD_PATH")

    if not all([base_url, database, username, password]):
        raise RuntimeError("MINERVA_BASE_URL / MINERVA_DATABASE / MINERVA_USERNAME / MINERVA_PASSWORD must be set.")

    # ---------------------------------------------------------
    # 2️⃣ Client 생성
    # ---------------------------------------------------------
    client = MinervaCLIClient(
        base_url=base_url,
        database=database,
        username=username,
        password=password,
        auth_mode="Explicit",
        name="TEST_CLIENT",
        interactive="None",
    )

    print("\n=== Client Created ===\n")

    # ---------------------------------------------------------
    # 3️⃣ Sign-in Test
    # ---------------------------------------------------------
    try:
        print("Signing in...")
        out = client.sign_in(force=True, local=local_path)
        print("Sign-in OK")
        print(out)
    except Exception as e:
        print("Sign-in FAILED")
        print(e)

    # ---------------------------------------------------------
    # 4️⃣ Download Test
    # ---------------------------------------------------------
    try:
        print("\nDownloading test item...")
        out = client.download(
            remote="ans_Data/C9FD71B09E3B4DCA8B36784E0A8FFD2A",
            local=local_path,
        )
        print("Download OK")
        print(out)
    except Exception as e:
        print("Download FAILED")
        print(e)

    # ---------------------------------------------------------
    # 5️⃣ Local command Test
    # ---------------------------------------------------------
    try:
        print("\nChecking local status...")
        out = client.get_status(local=local_path)
        print("Local Status OK")
        print(out)
    except Exception as e:
        print("Local Status FAILED")
        print(e)

    # ---------------------------------------------------------
    # 6️⃣ Updating authentication configuration Test (예: Windows mode)
    # ---------------------------------------------------------
    try:
        print("\nSwitching auth mode to Windows...")
        client.set_auth(mode="Windows")
        print("Auth switched successfully.")

        print("Signing in with Windows auth...")
        out = client.sign_in(force=True, local=local_path)
        print("Sign-in (Windows) OK")
        print(out)

    except Exception as e:
        print("Auth switch FAILED")
        print(e)

    # ---------------------------------------------------------
    # 7️⃣ Sign-out Test
    # ---------------------------------------------------------
    try:
        print("\nSigning out...")
        out = client.sign_out(local=local_path)
        print("Sign-out OK")
        print(out)
    except Exception as e:
        print("Sign-out FAILED")
        print(e)