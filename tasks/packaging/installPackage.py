import copy
from cumulusci.tasks.salesforce.install_package_version import InstallPackageVersion
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.core.config import TaskConfig
from tasks.packaging.getDependencies import GetDependencies, SFDXPackages
from cumulusci.salesforce_api.package_install import install_package_by_version_id, PackageInstallOptions

install_options = copy.deepcopy(InstallPackageVersion.task_options)
install_options["name"]["required"] = True
install_options["namespace"]["required"] = False


class InstallPackageDeps(BaseSalesforceApiTask):
    task_options = {
        "name": {
            "description": "The name of the package to install",
            "required": True,
        },
        "version": {
            "description": "The version of the package to install",
            "required": False,
        },
        "query_only": {
            "description": "The version of the package to install",
            "required": False,
            "default": False,
        },
    }
    root_package = None
    packages = None
    query_only = False

    def _init_options(self, kwargs):
        super(InstallPackageDeps, self)._init_options(kwargs)
        self.package_name = self.options['name'].strip()
        self.logger.info(f"Task Options: {self.options}")
        if "query_only" in self.options:
            self.query_only = self.options['query_only']
        self.sfdx_packages = SFDXPackages(self.project_config)
        for package in self.sfdx_packages.packages:
            if package.package == self.options["name"]:
                self.root_package = package
                break
        if self.root_package is None:
            self.logger.error(f"Package {self.package_name} not found in sfdx-project.json")
            exit(1)

    def _create_tasks_for_deps(self, list_of_versionIds):
        default_options = PackageInstallOptions()
        for dependency in list_of_versionIds:
            if not self.query_only:
                install_package_by_version_id(project_config=self.project_config, 
                                              org_config=self.org_config,
                                              version_id=dependency,
                                              install_options=default_options)
            
            # task_options = {
            #     "command": f"package install --package {dependency}"
            # }

            # task = SFDXOrgTask(self.project_config,
            #                    TaskConfig({"options": task_options}),
            #                    self.org_config)
            # if not self.query_only:
            #     task()
            else:
                self.logger.info(f"""
    Would have run task: install_package_by_version_id(
    project_config={self.project_config}, 
    org_config={self.org_config},
    version_id={dependency},
    install_options={default_options})
    """)
            
    def _run_task(self):
        self.options['package_name'] = self.options['name']
        task_options = {
            "name": self.options['name'],
            "version": self.options['version'] if "version" in self.options else "latest"
        }
        install_task = InstallPackageVersion(
            project_config=self.project_config,
            task_config=TaskConfig({"options": task_options}),
            org_config=self.org_config)
        get_deps = GetDependencies(self.project_config, TaskConfig({"options": self.options}), self.org_config)
        results = get_deps()
        deps = results['dependencies'] if 'dependencies' in results else None
        if deps is None:
            self.logger.info(f"No dependencies found for package {self.options['name']}")
        else:            
            self.logger.info(f"Found dependencies: {deps}")
            self._create_tasks_for_deps(deps)
        
        if self.query_only:
            self.logger.info(f"Would have run task: {install_task}")
            self.logger.info("Query only was set. No packages were installed.")
        else:
            install_task()
