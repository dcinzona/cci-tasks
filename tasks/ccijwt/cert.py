# Task to create a PEM certificate for a JWT client.
import os
from cumulusci.core.tasks import BaseTask
from utilities.selfsigned import generate_selfsigned_cert


class CreateCert(BaseTask):
    task_options = {
        "hostname": {
            "description": "The domain for self-signed certificate generation",
            "required": True,
        },
        "dir": {
            "description": "If provided, the directory where the command "
            "should be run from."
        },
        "interactive": {
            "description": "If True, the command will use stderr, stdout, "
            "and stdin of the main process."
            "Defaults to False."
        },
    }

    def _init_options(self, kwargs):
        super(CreateCert, self)._init_options(kwargs)
        if "dir" not in self.options or not self.options["dir"]:
            self.options["dir"] = ".jwt/test"
        if "interactive" not in self.options:
            self.options["interactive"] = False

        os.makedirs(self.options["dir"], exist_ok=True)

    def _run_task(self):
        self.logger.info("Creating self-signed certificate")
        cert_pem, key_pem = generate_selfsigned_cert(hostname=self.options["hostname"])
        cert_path = os.path.join(self.options["dir"], "server.crt")
        key_path = os.path.join(self.options["dir"], "server.key")

        self.logger.info("Writing cert to {}".format(cert_path))
        with open(
            cert_path,
            "wb+",
        ) as f:
            f.write(cert_pem)

        self.logger.info("Writing key to {}".format(key_path))
        with open(key_path, "wb+") as f:
            f.write(key_pem)

        self.logger.info(
            f"\nCert uploaded with Connected App: \n'{self.readCert(cert_path)}' \n"
        )
        self.logger.info(f"Key used for JWT: \n'{self.readCert(key_path)}'")

        self.logger.info("\nDone")

    def readCert(self, cert_path):
        with open(cert_path, "r", encoding="utf-8") as f:
            cert = ""
            for line in f.readlines():
                cert += line.strip() if line.find("-----") == -1 else ""
            return cert
