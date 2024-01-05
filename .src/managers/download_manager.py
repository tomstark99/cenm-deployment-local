import os
from utils import deprecated, SystemInteract

class DownloadManager:
    """Download manager for interacting with wget or curl.

    Args:
        username:
            The username to use for the download.
        password:
            The password to use for the download.

    """
    
    def __init__(self, 
        username: str, 
        password: str
    ):
        self.username = username
        self.password = password
        self.wget = False #self._is_wget_installed()
        self.sysi = SystemInteract()

    @deprecated
    def _is_wget_installed(self) -> bool:
        """Checks if wget is installed on host machine.

        Returns:
            True installed False if not.

        Deprecating use of wget in favor of curl
        """
        return os.system('wget --version > /dev/null 2>&1') == 0

    def _get_md5sum(self, url: str) -> str:
        return self.sysi.run_get_stdout(f'curl -L --progress-bar -u {self.username}:{self.password} {url} | md5sum | cut -d " " -f 1')

    def _validate_download(self, url: str) -> bool:
        """Check the md5sum of the downloaded file against the one that would be downloaded

        Args:
            url:
                The url to download the file from.

        Returns:
            True if the md5sums do not match, False otherwise.
        
        """
        artifact = url.split("/")[-1]
        print(f'Validating {artifact}')
        return not self.check_md5sum(artifact, url)

    def check_md5sum(self, artifact_path: str, artifact_url: str) -> bool:
        return self.sysi.run_get_stdout(f'md5sum {artifact_path} | cut -d " " -f 1') == self._get_md5sum(artifact_url)

    def download(self, url: str) -> bool:
        """Download a file from a given url using wget or curl.

        Args:
            url: 
                The url to download the file from.

        Returns:
            True if the download failed, False otherwise.

        """
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
        # return not self._validate_download(url)
