from ftplib import FTP_TLS
from pathlib import Path


class SecureFTPClient:
	def __init__(self, host: str, port: int = 21):
		self.host = host
		self.port = port
		self.ftp = FTP_TLS()

	def login(self, login_name, password):
		self.ftp.connect(self.host, self.port)
		self.ftp.auth()
		self.ftp.prot_p()
		self.ftp.login(login_name, password)

	def list_files(self, remote_directory='.'):
		return self.ftp.mlsd(remote_directory)

	def store_file(self, local_path, remote_path):
		with open(local_path, 'rb') as local_file:
			self.ftp.storbinary(f'STOR {remote_path}', local_file)

	def close(self):
		self.ftp.quit()


if __name__ == "__main__":
	# Example usage:
	ftp_client = SecureFTPClient('ftp.example.com', 21)
	ftp_client.login('your_username', 'your_password')

	# Example 1: Retrieve list of files in the root directory
	file_list = ftp_client.list_files()
	print("List of files in the root directory:")
	for file_info in file_list:
		print(file_info)

	# Example 2: Store a local file to the remote directory
	local_file_path = Path('local_file.txt')
	remote_file_path = 'remote_directory/remote_file.txt'
	ftp_client.store_file(local_file_path, remote_file_path)

	ftp_client.close()
