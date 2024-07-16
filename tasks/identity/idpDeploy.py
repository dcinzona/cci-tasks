import copy
import os

from cumulusci.tasks.salesforce import Deploy
from cumulusci.utils import temporary_dir

deploy_options = copy.deepcopy(Deploy.task_options)
deploy_options["path"][
    "required"
] = False


CONNECTED_APP = """<?xml version="1.0" encoding="UTF-8"?>
<ConnectedApp xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Scratch Subscriber</label>
    <contactEmail>noreply@salesforce.com</contactEmail>
    <samlConfig>
        <acsUrl>{acs_url}</acsUrl>
        <encryptionType>AES_128</encryptionType>
        <entityUrl>{acs_url}</entityUrl>
        <issuer>{idp_url}</issuer>
        <samlNameIdFormat>EmailAddress</samlNameIdFormat>
        <samlSigningAlgoType>SHA1</samlSigningAlgoType>
        <samlSubjectType>FederationId</samlSubjectType>
    </samlConfig>
</ConnectedApp>"""

PACKAGE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>*</members>
        <name>ConnectedApp</name>
    </types>
    <version>59.0</version>
</Package>"""


class deployMetadata(Deploy):
    task_options = deploy_options

    def _init_options(self, kwargs):
        self.idpOrgConfig = self.project_config.keychain.get_org('idp')
        self.spOrgConfig = self.project_config.keychain.get_org('sp')
        self.spOrgId = self.project_config.keychain.get_org('sp').org_id
        self.idpOrgId = self.project_config.keychain.get_org('idp').org_id
        super()._init_options(kwargs)

    def _build_package(self):
        connected_app_path = "connectedApps"
        os.mkdir(connected_app_path)
        connapp = CONNECTED_APP.format(
            acs_url=self.spOrgConfig.instance_url,
            idp_url=self.idpOrgConfig.instance_url
            )
        self.logger.info("Connected App: %s", connapp)
        with open(
            os.path.join(connected_app_path, "Scratch_Subscriber.connectedApp"),
            "w",
        ) as f:
            f.write(connapp)
        with open("package.xml", "w") as f:
            f.write(PACKAGE_XML)

    def _run_task(self):
        with temporary_dir() as tempdir:
            self.tempdir = tempdir
            self.options["path"] = tempdir
            self.task_options["path"] = tempdir
            self._build_package()
            super()._run_task()
