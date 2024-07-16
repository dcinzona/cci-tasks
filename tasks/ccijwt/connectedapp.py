import os
from cumulusci.utils import temporary_dir
import cumulusci.tasks.connectedapp as conapp
from cumulusci.tasks.connectedapp import CreateConnectedApp as _CreateConnectedApp
from utilities.envparser import getCert

CONNECTED_APP = """<?xml version="1.0" encoding="UTF-8"?>
<ConnectedApp xmlns="http://soap.sforce.com/2006/04/metadata">
    <contactEmail>{email}</contactEmail>
    <label>{label}</label>
    <oauthConfig>
        <callbackUrl>http://localhost:8080/callback</callbackUrl>
        <certificate>{server_crt}</certificate>
        <consumerKey>{client_id}</consumerKey>
        <consumerSecret>{client_secret}</consumerSecret>
        <isAdminApproved>true</isAdminApproved>
        <isConsumerSecretOptional>false</isConsumerSecretOptional>
        <isIntrospectAllTokens>false</isIntrospectAllTokens>
        <isSecretRequiredForRefreshToken>true</isSecretRequiredForRefreshToken>
        <scopes>Api</scopes>
        <scopes>Full</scopes>
        <scopes>Web</scopes>
        <scopes>RefreshToken</scopes>
    </oauthConfig>
    <oauthPolicy>
        <ipRelaxation>ENFORCE</ipRelaxation>
        <refreshTokenPolicy>infinite</refreshTokenPolicy>
    </oauthPolicy>
    <permissionSetName>{}_USER_PS</permissionSetName>
</ConnectedApp>"""

PERM_SET = """<?xml version="1.0" encoding="UTF-8"?>
<PermissionSet xmlns="http://soap.sforce.com/2006/04/metadata">
    <hasActivationRequired>false</hasActivationRequired>
    <label>{label}_USER_PS</label>
</PermissionSet>"""

PACKAGE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>*</members>
        <name>ConnectedApp</name>
    </types>
    <types>
        <members>*</members>
        <name>PermissionSet</name>
    </types>
    <version>54.0</version>
</Package>"""


class CreateConnectedApp(_CreateConnectedApp):
    conapp.CONNECTED_APP = CONNECTED_APP
    conapp.PACKAGE_XML = PACKAGE_XML
    task_options = _CreateConnectedApp.task_options.copy()
    task_options["cert_path"] = {
        "description": "The file path to the PEM Cert to use in the connected app. (NOT the private key)",
        "required": True,
    }

    def _init_options(self, kwargs):
        self.client_id = None
        self.client_secret = None
        kwargs["command"] = "force:mdapi:deploy --wait {}".format(
            _CreateConnectedApp.deploy_wait
        )
        super(CreateConnectedApp, self)._init_options(kwargs)
        self.server_crt = getCert(self.options["cert_path"], True)

    def _build_package(self):
        connected_app_path = "connectedApps"
        permission_set_path = "permissionsets"
        os.mkdir(connected_app_path)
        self._generate_id_and_secret()
        with open(
            os.path.join(connected_app_path, self.options["label"] + ".connectedApp"),
            "w",
        ) as f:
            f.write(self._getConnAppXml())
        with open(
            os.path.join(
                permission_set_path,
                "{}_USER_PS".format(self.options["label"]) + ".permissionset",
            ),
            "w",
        ) as f:
            f.write(PERM_SET.format(label=self.options["label"]))
        with open("package.xml", "w") as f:
            f.write(PACKAGE_XML)

    def _run_task(self):
        self.logger.info("Creating Connected App...")
        self._generate_id_and_secret()
        self.logger.info(self._getConnAppXml())
        os.putenv("SFDX_CLIENT_ID", self.client_id)
        os.putenv("SFDX_HUB_KEY", self.server_crt)

        with temporary_dir() as tempdir:
            self.tempdir = tempdir
            self._build_package()

    def _getConnAppXml(self):
        return CONNECTED_APP.format(
            label=self.options["label"],
            email=self.options["email"],
            client_id=self.client_id,
            client_secret=self.client_secret,
            server_crt=self.server_crt,
        )
