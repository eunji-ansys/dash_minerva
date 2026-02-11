import subprocess
import os
from ..utils.decorators import log

class CLIExecutor:
    def __init__(self, executable_path):
        self.path = executable_path

    @log("CLI Execute Mode: {mode} with {fragments}")
    def run(self, mode, fragments, auth_context: dict = None):
        """
        auth_context를 통해 토큰이나 인증 정보를 환경 변수로 주입합니다.
        """
        command = [self.path, mode] + fragments + ["--output", "stream://stdout"]

        # 시스템 기본 환경 변수 복사
        env = os.environ.copy()
        if auth_context:
            # Minerva CLI가 인식하는 표준 환경 변수들
            if 'token' in auth_context:
                env["ANS_MINERVA_AUTH__TOKEN"] = auth_context['token']
            if 'password' in auth_context:
                env["ANS_MINERVA_AUTH__PASSWORD"] = auth_context['password']
            env["ANS_MINERVA_URL"] = auth_context.get('url', '')
            env["ANS_MINERVA_DATABASE"] = auth_context.get('db', '')

        try:
            result = subprocess.run(command, capture_output=True, text=True, env=env, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise ValueError(f"CLI Error: {e.stderr}")