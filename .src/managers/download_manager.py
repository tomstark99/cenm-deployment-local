import os

class DownloadManager():
    
    def __init__(self, username, password, wget):
        self.username = username
        self.password = password
        self.wget = self._is_wget_installed()

    def _is_wget_installed() -> bool:
    return os.system('wget --version > /dev/null 2>&1') == 0

    def download(self, url) -> bool:
        if self.wget:
            cmd = os.system(f'wget -q --show-progress --user {self.username} --password {self.password} {url}')
            if cmd != 0:
                cmd2 = os.system(f'wget --progress=bar:force:noscroll --user {self.username} --password {self.password} {url}')
                if cmd2 != 0:
                    return True
        else:
            cmd = os.system(f'curl --progress-bar -u {self.username}:{self.password} -O {url}')
            if cmd != 0:
                return True
        return False
