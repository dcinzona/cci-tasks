from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
from cumulusci.core.config.util import get_devhub_config
import pprint as pp
from tasks.utils.packageQueryClasses import PackageVersion, SFDXPackageBase, package_query_fields, SFDXPackages, PackageDependencyIds


class GetDependencies(BaseSalesforceApiTask):
    task_options = {
        "package_name": {
            "description": "The name of the package to install",
            "required": True,
        },
        "package_version": {
            "description": "The version of the package to install",
            "required": False,
        }
    }
    root_package = None
    # We do use a Salesforce org, but it's the dev hub obtained using get_devhub_config,
    # so the user does not need to specify an org on the CLI
    salesforce_task = False

    # Since self.org_config is unused, don't try to refresh its token
    def _update_credentials(self):
        pass

    def _init_task(self) -> None:
        self.tooling = get_simple_salesforce_connection(
            self.project_config,
            get_devhub_config(self.project_config),
            api_version=self.api_version,
            base_url="tooling",
        )

    def _init_options(self, kwargs):
        super(GetDependencies, self)._init_options(kwargs)
        self.package_name = self.options['package_name'].strip()
        self.sfdx_packages = SFDXPackages(self.project_config)
        for package in self.sfdx_packages.packages:
            if package.package == self.options["package_name"]:
                self.root_package = package
                break
        if self.root_package is None:
            self.logger.error(f"Package {self.package_name} not found in sfdx-project.json")
            exit(1)

    def _query_dev_hub(self, package: SFDXPackageBase = None, version: str = 'latest'):
        query = f"SELECT {','.join(package_query_fields)} FROM Package2Version WHERE Package2.Name = '{package.package}'"
        self.logger.debug(f"\nQuerying Dev Hub for package: {package}")
        self.logger.debug(f"Query: {query}\n")
        result = self.tooling.query(query)
        arr = [PackageVersion(x) for x in result["records"]]
        if len(arr) == 0:
            self.logger.info(f"No package versions found for package {package.package}")
            return None
        sorted_arr = sorted(arr, key=lambda x: x.version)
        self.logger.debug(f"Found Package Versions:\n{pp.pformat(sorted_arr)}")
        if version == "latest":
            # return last element in array
            return sorted_arr[-1]
        else:
            filtered = [x for x in sorted_arr if x.version == version]
            return filtered[-1] if len(filtered) > 0 else sorted_arr[-1]
    
    def _query_dependencies(self, package_version_id):
        if package_version_id is None:
            return []
        self.logger.info(f"Querying dependencies for package version: {package_version_id}")
        query = f"SELECT Dependencies FROM SubscriberPackageVersion WHERE Id = '{package_version_id}'"
        self.logger.info(f"Query: {query}\n")
        result = self.tooling.query(query)
        return [PackageDependencyIds(r['Dependencies']).subscriberPackageVersionIds for r in result["records"]]

    def _get_latest_available_version(self, package: SFDXPackageBase = None):
        if package is None:
            package = self.root_package
        result = self._query_dev_hub(package)
        return result[-1] if result is not None else None

    def _run_task(self):
        self.logger.info(f"Getting dependencies for package {self.package_name}")
        latest_package_version = None
        dependencies = []
        if self.root_package.subscriberPackageVersionId is None:
            latest_package_version = self._get_latest_available_version(self.root_package)
            if latest_package_version is None:
                self.logger.error(f"No published package versions found for package {self.package_name}")
                for dep in self.root_package.dependencies:
                    self.logger.error(f"SFDX Project File Dependency: {dep}")
                    package = self._query_dev_hub(dep)
                    if package is not None:
                        dependencies.append(package.SubscriberPackageVersionId)
                        child_deps = self._query_dependencies(package.SubscriberPackageVersionId)
                        for child in child_deps:
                            dependencies.extend(child)
        else:
            dependencies = self._query_dependencies(latest_package_version)

        for dep in dependencies:
            self.logger.info(f"Dependency: {dep}")    
        
        unique_deps = set(dependencies)
        uniques = list(unique_deps)
        self.return_values = {"dependencies": uniques}
        self.logger.info(f"Dependencies found for package '{self.root_package.package}':\n {pp.pformat(dependencies)}")
        return self.return_values
