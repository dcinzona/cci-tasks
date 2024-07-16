import os
import copy

from tasks.identity.idpDeploy import Deploy
from cumulusci.salesforce_api.metadata import ApiRetrieveUnpackaged
from cumulusci.tasks.salesforce import BaseRetrieveMetadata


from cumulusci.utils import temporary_dir
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
deploy_options = copy.deepcopy(Deploy.task_options)
deploy_options["path"][
    "required"
] = False

METADATA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<SamlSsoConfig xmlns="http://soap.sforce.com/2006/04/metadata">
    <executionUserId>{user_id}</executionUserId>
    <identityLocation>SubjectNameId</identityLocation>
    <identityMapping>FederationId</identityMapping>
    <issuer>{idp_org_url}</issuer>
    <loginUrl>{idp_org_url}/idp/endpoint/HttpRedirect</loginUrl>
    <name>Scratch Org IDP</name>
    <oauthTokenEndpoint>{sp_org_url}/services/oauth2/token</oauthTokenEndpoint>
    <redirectBinding>true</redirectBinding>
    <requestSignatureMethod>1</requestSignatureMethod>
    <requestSigningCertId>{cert_id}</requestSigningCertId>
    <salesforceLoginUrl>{sp_org_url}</salesforceLoginUrl>
    <samlEntityId>{sp_org_url}</samlEntityId>
    <samlJitHandlerId>{jit_apex_class}</samlJitHandlerId>
    <samlVersion>SAML2_0</samlVersion>
    <useConfigRequestMethod>true</useConfigRequestMethod>
    <useSameDigestAlgoForSigning>true</useSameDigestAlgoForSigning>
    <userProvisioning>true</userProvisioning>
    <validationCert>{idp_cert}</validationCert>
</SamlSsoConfig>"""

PACKAGE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>*</members>
        <name>SamlSsoConfig</name>
    </types>
    <version>59.0</version>
</Package>"""


class deploySSO(Deploy):

    task_options = deploy_options
    api_version = None
    cert_id = None
    jit_hanlder = None

    def _init_task(self):
        super()._init_task()
        self.sf = self._init_api()
        self.tooling = self._init_api("tooling")

    def _init_api(self, base_url=None):
        rv = get_simple_salesforce_connection(
            self.project_config,
            self.org_config,
            api_version=self.api_version,
            base_url=base_url,
        )

        return rv

    def _init_options(self, kwargs):
        self.spOrgConfig = self.project_config.keychain.get_org('sp')
        self.idpOrgConfig = self.project_config.keychain.get_org('idp')
        self.idp_url = self.idpOrgConfig.instance_url
        self.sp_url = self.spOrgConfig.instance_url
        self.user_id = self.org_config.user_id[:15]
        super()._init_options(kwargs)

    def _get_cert_id(self, certName='SelfSignedCert') -> str:
        if self.cert_id:
            return self.cert_id
        # get the cert id from the org
        query = f"SELECT Id FROM Certificate WHERE DeveloperName = '{certName}' LIMIT 1"
        self.cert_id = self._get_record_id_from_query(query, self.tooling)
        return self.cert_id

    def _get_jit_class_id(self, name='JitHandler') -> str:
        if self.jit_hanlder:
            return self.jit_hanlder
        # get the cert id from the org
        query = f"SELECT Id FROM ApexClass WHERE Name = '{name}' LIMIT 1"
        self.jit_hanlder = self._get_record_id_from_query(query, self.tooling)
        return self.jit_hanlder

    def _get_record_id_from_query(self, query, api):
        for result in api.query_all(query)["records"]:
            return result["Id"][:15]
        self.logger.error(f"No results for query {query}")
        return None

    def _build_package(self):
        metapath = "samlssoconfigs"
        os.mkdir(metapath)
        metaxml = METADATA_XML.format(
            user_id=self.user_id,
            idp_org_url=self.idp_url,
            sp_org_url=self.sp_url,
            cert_id=self._get_cert_id(),
            jit_apex_class=self._get_jit_class_id(),
            idp_cert=self.cert,
        )
        with open(
            os.path.join(metapath, 'IdP' + ".samlssoconfig"),
            "w",
        ) as f:
            self.logger.info(f"{metapath}: {metaxml}")
            f.write(metaxml)
        with open("package.xml", "w") as f:
            f.write(PACKAGE_XML)
    
    def _get_cert_from_idp(self):
        retrieve_cert = RetrieveCert(project_config=self.project_config,
                                     task_config=self.task_config,
                                     org_config=self.idpOrgConfig,
                                     logger=self.logger)
        retrieve_cert()
        self.cert = retrieve_cert.get_cert()

    def _run_task(self):
        self._get_cert_from_idp()
        with temporary_dir() as tempdir:
            if not self.cert:
                self.logger.error("No cert found")
                return
            self.tempdir = tempdir
            self._build_package()
            self.options["path"] = tempdir
            self.task_options["path"] = tempdir
            super()._run_task()


retrieve_unpackaged_options = BaseRetrieveMetadata.task_options.copy()
retrieve_unpackaged_options["path"][
    "required"
] = False


class RetrieveCert(BaseRetrieveMetadata):
    api_class = ApiRetrieveUnpackaged
    api_version = "59.0"
    task_options = retrieve_unpackaged_options

    def _init_options(self, kwargs):
        kwargs["package_xml"] = 'manifest/certs.xml'
        super(RetrieveCert, self)._init_options(kwargs)
        if "package_xml" in self.options:
            with open(self.options["package_xml"], "r") as f:
                self.options["package_xml_content"] = f.read()

    def _run_task(self):
        with temporary_dir() as tempdir:
            self.options["path"] = tempdir
            super()._run_task()
            # read directory content
            self.logger.info(f"Tempdir: {tempdir}")
            self.logger.info(f"Contents: {os.listdir(tempdir)}")
            # check if certs directory exists
            if not os.path.exists(os.path.join(tempdir, 'certs')):
                self.logger.error(f"Cert directory not found in {tempdir}")
                return
            # read the cert
            with open(os.path.join(tempdir, 'certs', 'SelfSignedCert.crt'), 'r') as f:
                self.cert = f.read()
                self.cert = self.cert.replace('-----BEGIN CERTIFICATE-----\n', '')
                self.cert = self.cert.replace('-----END CERTIFICATE-----\n', '')
                # self.cert = self.cert.replace('\n', '')
            self.logger.info(f"Cert: {self.cert}")
    
    def get_cert(self):
        return self.cert

    def _get_api(self):
        return self.api_class(
            self, self.options["package_xml_content"], self.options.get("api_version")
        )
