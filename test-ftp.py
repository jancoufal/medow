import logging
import mftp
from ftplib import FTP_TLS


def main():
	logger = logging.getLogger("mftp")
	ftp = mftp.SecureFTPClient(logger, "192.168.1.103")
	ftp.login("medow", "zMFt9LriOXt4DQrc")

	for f in ftp.list_files():
		print(f"{f=}")

	print("done")

	ftp.close()


def main2():
	ftp = FTP_TLS("192.168.1.103")
	ftp.auth()
	ftp.prot_p()
	ftp.login("medow", "zMFt9LriOXt4DQrc")

	for f in ftp.mlsd("."):
		print(f"{f=}")

	ftp.close()


if __name__ == "__main__":
	main2()
