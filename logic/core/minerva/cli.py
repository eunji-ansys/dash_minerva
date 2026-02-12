import os
import logging
import subprocess
import shlex
import json
from dataclasses import dataclass
from typing import List, Dict, Optional, Literal, Tuple, Iterable, Union, Any

# Optional: python-dotenv (pip install python-dotenv)
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


# -------------------------------------------------------------------
# Logging Configuration
# -------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger("MinervaCLI")


# -------------------------------------------------------------------
# Type Definitions
# -------------------------------------------------------------------
AuthMode = Literal["Explicit", "Impersonate", "Refresh_Token", "Windows"]
InteractiveMode = Literal["None", "Console", "Graphical"]
OverwriteMode = Literal["Error", "Overwrite", "Append", "Ignore", "Snapshot"]
SelectMode = Literal["SaveFile", "SelectFile", "SelectFolder", "SelectFileFolder"]


# -------------------------------------------------------------------
# Custom Exception
# -------------------------------------------------------------------
class MinervaCliError(RuntimeError):
    """
    Raised when the Minerva CLI execution fails.
    Contains execution metadata for debugging.
    """

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
            f"STDERR: {self.stderr.strip()}"
        )


# -------------------------------------------------------------------
# Utility Functions (Pure)
# -------------------------------------------------------------------
def _listify(value: Union[str, Iterable[str], None]) -> List[str]:
    """Normalize string or iterable into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _mask_env(env: Dict[str, str]) -> Dict[str, str]:
    """Mask sensitive values for logging."""
    masked = dict(env)
    for key in masked:
        if "PASSWORD" in key or "TOKEN" in key:
            masked[key] = "***"
    return masked


def build_common_args(
    *,
    url: str,
    interactive: InteractiveMode = "None",
    local: Optional[str] = None,
    ui_theme: Optional[str] = None,
    output: Optional[str] = None,
) -> List[str]:
    """
    Build common CLI arguments shared across commands.
    """
    args: List[str] = ["--url", url, "--interactive", interactive]
    if local:
        args += ["--local", local]
    if ui_theme:
        args += ["--ui-theme", ui_theme]
    if output:
        args += ["--output", output]
    return args


def build_auth_args(
    *,
    database: str,
    user: Optional[str] = None,
    mode: Optional[AuthMode] = None,
    certconfig: Optional[str] = None,
) -> List[str]:
    """
    Build authentication-related CLI flags (non-sensitive).
    """
    args = ["--auth:database", database]
    if user:
        args += ["--auth:user", user]
    if mode:
        args += ["--auth:mode", mode]
    if certconfig:
        args += ["--auth:certconfig", certconfig]
    return args


def build_auth_env(
    *,
    mode: AuthMode,
    password: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, str]:
    """
    Build environment variables for authentication secrets.
    """
    env: Dict[str, str] = {}
    if mode == "Explicit" and password:
        env["ANS_MINERVA_AUTH__PASSWORD"] = password
    elif mode == "Refresh_Token" and token:
        env["ANS_MINERVA_AUTH__TOKEN"] = token
    return env


def build_remotes_args(remote: Union[str, Iterable[str], None]) -> List[str]:
    """Build --remote arguments."""
    args: List[str] = []
    for r in _listify(remote):
        args += ["--remote", r]
    return args


def build_globs_args(globs: Union[str, Iterable[str], None]) -> List[str]:
    """Build --glob arguments."""
    args: List[str] = []
    for g in _listify(globs):
        args += ["--glob", g]
    return args


# -------------------------------------------------------------------
# Authentication Context
# -------------------------------------------------------------------
@dataclass(frozen=True)
class CLIAuthContext:
    """
    Authentication context.
    The database field is optional; if not provided,
    the client's default database will be used.
    """

    mode: AuthMode = "Explicit"
    user: Optional[str] = None
    database: Optional[str] = None

    password: Optional[str] = None          # Used for Explicit mode
    token: Optional[str] = None             # Used for Refresh_Token mode
    certconfig: Optional[str] = None        # Used for Impersonate mode


# -------------------------------------------------------------------
# Main CLI Client
# -------------------------------------------------------------------
class MinervaCLIClient:
    """
    Python wrapper for AnsysMinerva_CLI.exe.
    """

    def __init__(
        self,
        url: str,
        database_name: str,
        exe_path: Optional[str] = None,
        *,
        default_interactive: InteractiveMode = "None",
        default_output: Optional[str] = "stream://stdout",
    ):
        self.url = url
        self.db = database_name
        self.exe = exe_path or os.environ.get("ANS_MINERVA_CLI")
        self.default_interactive = default_interactive
        self.default_output = default_output

        if not self.exe or not os.path.exists(self.exe):
            raise FileNotFoundError(
                f"CLI Executable not found: {self.exe}\n"
                f"- Set exe_path explicitly, OR\n"
                f"- Set environment variable ANS_MINERVA_CLI to the full path of AnsysMinerva_CLI.exe"
            )

    # -------------------------------------------------------------------
    # Internal Execution Method
    # -------------------------------------------------------------------
    def _run(
        self,
        command: str,
        fragments: List[str],
        *,
        extra_env: Optional[Dict[str, str]] = None,
        check: bool = True,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """
        Execute CLI command.
        """
        full_command = [self.exe, command] + fragments
        cmd_str = " ".join(shlex.quote(str(a)) for a in full_command)

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        logger.debug("=" * 70)
        logger.debug(f"[EXECUTE] {cmd_str}")
        if extra_env:
            logger.debug(f"[ENV] {_mask_env(extra_env)}")
        logger.debug("=" * 70)

        cp = subprocess.run(full_command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)

        if check and cp.returncode != 0:
            raise MinervaCliError(
                f"Minerva CLI failed: {command}",
                returncode=cp.returncode,
                stdout=cp.stdout or "",
                stderr=cp.stderr or "",
                command=full_command,
            )

        if parse_json:
            return json.loads(cp.stdout or "")

        return cp.stdout or ""

    # -------------------------------------------------------------------
    # Auth Builder + Validation
    # -------------------------------------------------------------------
    def _validate_auth(self, auth: CLIAuthContext) -> None:
        """
        Validate that required auth inputs exist for each auth mode.
        Fails fast before executing any CLI commands.
        """
        if auth.mode == "Explicit":
            if not auth.password:
                raise ValueError("Explicit mode requires password (CLIAuthContext.password).")
            if auth.token or auth.certconfig:
                raise ValueError("Explicit mode must not use token or certconfig.")
        elif auth.mode == "Refresh_Token":
            if not auth.token:
                raise ValueError("Refresh_Token mode requires token (CLIAuthContext.token).")
            if auth.password or auth.certconfig:
                raise ValueError("Refresh_Token mode must not use password or certconfig.")
        elif auth.mode == "Impersonate":
            if not auth.certconfig:
                raise ValueError("Impersonate mode requires certconfig path (CLIAuthContext.certconfig).")
            if auth.password or auth.token:
                raise ValueError("Impersonate mode must not use password or token.")
        elif auth.mode == "Windows":
            if auth.password or auth.token or auth.certconfig:
                raise ValueError("Windows mode must not use password, token, or certconfig.")

    def _build_auth(self, auth: CLIAuthContext) -> Tuple[List[str], Dict[str, str]]:
        """
        Merge client default database with auth context and build args/env.
        """
        self._validate_auth(auth)

        database_to_use = auth.database or self.db
        certconfig = auth.certconfig if auth.mode == "Impersonate" else None

        args = build_auth_args(
            database=database_to_use,
            user=auth.user,
            mode=auth.mode,
            certconfig=certconfig,
        )
        env = build_auth_env(
            mode=auth.mode,
            password=auth.password,
            token=auth.token,
        )
        return args, env

    def _build_common(
        self,
        *,
        local: Optional[str],
        ui_theme: Optional[str],
        output: Optional[str],
        interactive: Optional[InteractiveMode],
    ) -> List[str]:
        """
        Build common args using client defaults when values are not provided.
        """
        return build_common_args(
            url=self.url,
            interactive=interactive or self.default_interactive,
            local=local,
            ui_theme=ui_theme,
            output=output if output is not None else self.default_output,
        )

    # -------------------------------------------------------------------
    # Public Commands
    # -------------------------------------------------------------------
    def sign_in(
        self,
        auth: CLIAuthContext,
        *,
        force: bool = False,
        local: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """
        Sign in to Ansys Minerva.
        Note: --force is only valid for sign-in.
        """
        common = self._build_common(local=local, ui_theme=ui_theme, output=output, interactive=interactive)
        auth_args, auth_env = self._build_auth(auth)

        action: List[str] = []
        if force:
            action.append("--force")

        return self._run("sign-in", common + auth_args + action, extra_env=auth_env, parse_json=parse_json)

    def sign_out(
        self,
        *,
        local: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Sign out from Ansys Minerva."""
        common = self._build_common(local=local, ui_theme=ui_theme, output=output, interactive=interactive)
        return self._run("sign-out", common, parse_json=parse_json)

    def claim(
        self,
        remote: Union[str, Iterable[str]],
        auth: CLIAuthContext,
        *,
        globs: Union[str, Iterable[str], None] = None,
        local: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Claim one or more remote items for exclusive editing."""
        common = self._build_common(local=local, ui_theme=ui_theme, output=output, interactive=interactive)
        auth_args, auth_env = self._build_auth(auth)

        action = build_globs_args(globs) + build_remotes_args(remote)
        return self._run("claim", common + auth_args + action, extra_env=auth_env, parse_json=parse_json)

    def unclaim(
        self,
        remote: Union[str, Iterable[str]],
        auth: CLIAuthContext,
        *,
        globs: Union[str, Iterable[str], None] = None,
        local: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Unclaim one or more remote items."""
        common = self._build_common(local=local, ui_theme=ui_theme, output=output, interactive=interactive)
        auth_args, auth_env = self._build_auth(auth)

        action = build_globs_args(globs) + build_remotes_args(remote)
        return self._run("unclaim", common + auth_args + action, extra_env=auth_env, parse_json=parse_json)

    def download(
        self,
        remote: Union[str, Iterable[str]],
        auth: CLIAuthContext,
        *,
        local: Optional[str] = None,
        overwrite: OverwriteMode = "Overwrite",
        no_session: bool = False,
        content: bool = False,
        dependencies: Optional[bool] = None,
        filter: Optional[str] = None,
        path: Optional[str] = None,
        remote_start: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Download remote items to a local directory."""
        common = self._build_common(local=local, ui_theme=ui_theme, output=output, interactive=interactive)
        auth_args, auth_env = self._build_auth(auth)

        action: List[str] = ["--overwrite", overwrite]
        if no_session:
            action.append("--no-session")
        if content:
            action.append("--content")
        if dependencies is not None:
            action += ["--dependencies", "True" if dependencies else "False"]
        if filter:
            action += ["--filter", filter]
        if path:
            action += ["--path", path]
        if remote_start:
            action += ["--remote-start", remote_start]

        action += build_remotes_args(remote)
        return self._run("download", common + auth_args + action, extra_env=auth_env, parse_json=parse_json)

    def fetch_status(
        self,
        auth: CLIAuthContext,
        *,
        glob: Union[str, Iterable[str], None] = None,
        local: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Query Minerva for the latest information for local files."""
        common = self._build_common(local=local, ui_theme=ui_theme, output=output, interactive=interactive)
        auth_args, auth_env = self._build_auth(auth)

        action = build_globs_args(glob)
        return self._run("fetch-status", common + auth_args + action, extra_env=auth_env, parse_json=parse_json)

    def select_items(
        self,
        auth: CLIAuthContext,
        *,
        mode: SelectMode,
        filter: Optional[str] = None,
        dependencies: Optional[bool] = None,
        multi_select: Optional[bool] = None,
        remote_start: Optional[str] = None,
        remote: Union[str, Iterable[str], None] = None,
        local: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Select items in Minerva and output a JSON description."""
        common = self._build_common(local=local, ui_theme=ui_theme, output=output, interactive=interactive)
        auth_args, auth_env = self._build_auth(auth)

        action: List[str] = ["--mode", mode]
        if dependencies is not None:
            action += ["--dependencies", "True" if dependencies else "False"]
        if filter:
            action += ["--filter", filter]
        if multi_select is not None:
            action += ["--multiSelect", "True" if multi_select else "False"]
        if remote_start:
            action += ["--remote-start", remote_start]
        if remote:
            action += build_remotes_args(remote)

        return self._run("select-items", common + auth_args + action, extra_env=auth_env, parse_json=parse_json)

    def upload(
        self,
        remote: str,
        auth: CLIAuthContext,
        *,
        local: Optional[str] = None,
        glob: Union[str, Iterable[str], None] = None,
        overwrite: OverwriteMode = "Overwrite",
        no_session: bool = False,
        close_session: bool = False,
        override_minervaignore: Union[str, Iterable[str], None] = None,
        remote_start: Optional[str] = None,
        version_folders: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Upload files from a local directory to Minerva."""
        common = self._build_common(local=local, ui_theme=ui_theme, output=output, interactive=interactive)
        auth_args, auth_env = self._build_auth(auth)

        action: List[str] = ["--remote", remote, "--overwrite", overwrite]
        if no_session:
            action.append("--no-session")
        if close_session:
            action.append("--close-session")

        action += build_globs_args(glob)

        for x in _listify(override_minervaignore):
            action += ["--override-minervaignore", x]
        if remote_start:
            action += ["--remote-start", remote_start]
        if version_folders:
            action += ["--version-folders", version_folders]

        return self._run("upload", common + auth_args + action, extra_env=auth_env, parse_json=parse_json)

    # Commands that do not show auth/url in the provided help snippet.
    def get_local(
        self,
        path: str,
        *,
        local: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Return unified working directory information for a local file/folder."""
        args: List[str] = ["--path", path]
        args += ["--interactive", interactive or self.default_interactive]
        if local:
            args += ["--local", local]
        args += ["--output", output if output is not None else (self.default_output or "stream://stdout")]
        if ui_theme:
            args += ["--ui-theme", ui_theme]

        return self._run("get-local", args, parse_json=parse_json)

    def get_status(
        self,
        *,
        local: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Show which files have been staged for upload."""
        args: List[str] = []
        args += ["--interactive", interactive or self.default_interactive]
        if local:
            args += ["--local", local]
        args += ["--output", output if output is not None else (self.default_output or "stream://stdout")]
        if ui_theme:
            args += ["--ui-theme", ui_theme]

        return self._run("get-status", args, parse_json=parse_json)

    def stage(
        self,
        globs: Union[str, Iterable[str]],
        *,
        local: Optional[str] = None,
        override_minervaignore: Union[str, Iterable[str], None] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Stage files for upload based on glob patterns."""
        args: List[str] = build_globs_args(globs)
        for x in _listify(override_minervaignore):
            args += ["--override-minervaignore", x]

        args += ["--interactive", interactive or self.default_interactive]
        if local:
            args += ["--local", local]
        args += ["--output", output if output is not None else (self.default_output or "stream://stdout")]
        if ui_theme:
            args += ["--ui-theme", ui_theme]

        return self._run("stage", args, parse_json=parse_json)

    def unstage(
        self,
        globs: Union[str, Iterable[str]],
        *,
        local: Optional[str] = None,
        ui_theme: Optional[str] = None,
        output: Optional[str] = None,
        interactive: Optional[InteractiveMode] = None,
        parse_json: bool = False,
    ) -> Union[str, Any]:
        """Remove files from the staging list."""
        args: List[str] = build_globs_args(globs)

        args += ["--interactive", interactive or self.default_interactive]
        if local:
            args += ["--local", local]
        args += ["--output", output if output is not None else (self.default_output or "stream://stdout")]
        if ui_theme:
            args += ["--ui-theme", ui_theme]

        return self._run("unstage", args, parse_json=parse_json)


# -------------------------------------------------------------------
# Entry Point
# -------------------------------------------------------------------
if __name__ == "__main__":
    load_dotenv()

    client = MinervaCLIClient(
        url=os.getenv("MINERVA_URL"),
        database_name=os.getenv("MINERVA_DB")
    )

    auth = CLIAuthContext(
        mode="Explicit",
        user=os.getenv("MINERVA_USER"),
        password=os.getenv("MINERVA_PASS")
    )

     # Download JSON to stdout, parse if you want
    out = client.download(
        remote="ans_Data/C9FD71B09E3B4DCA8B36784E0A8FFD2A",
        auth=auth,
        local=os.getenv("TEMP_DOWNLOAD_PATH")
    )
    print(out)

    # logger.info("=== [1] SIGN-IN ===")
    # out1 = client.sign_in(auth, force=False, interactive="None", parse_json=False)
    # logger.info(out1.strip() or "(no stdout)")

    # # This may require a graphical/console UI depending on your environment.
    # # If you run in batch mode, it may fail unless all required options are provided.
    # logger.info("=== [2] SELECT-ITEMS (may open UI) ===")
    # try:
    #     out2 = client.select_items(
    #         auth,
    #         mode="SelectFileFolder",
    #         filter=None,
    #         interactive="Graphical",     # switch to "None" if you want strict batch mode
    #         parse_json=False,            # set True if stdout is guaranteed to be pure JSON
    #     )
    #     logger.info(out2.strip() or "(no stdout)")
    # except MinervaCliError as e:
    #     logger.error("select-items failed (often expected if UI is unavailable):")
    #     logger.error(str(e))

    # logger.info("=== [3] SIGN-OUT ===")
    # out3 = client.sign_out(interactive="None", parse_json=False)
    # logger.info(out3.strip() or "(no stdout)")
