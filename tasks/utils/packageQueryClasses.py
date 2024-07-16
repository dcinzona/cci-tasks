import json
from abc import ABC

package_query_fields = [
    "Id",
    "Package2.Name",
    "Name",
    "SubscriberPackageVersionId",
    "IsReleased",
    "ReleaseVersion",
    "MajorVersion",
    "MinorVersion",
    "PatchVersion",
    "BuildNumber",
    ]


class PrintableObject(ABC):
    def __json__(self):
        return json.dumps(
            self,
            default=lambda o: o.__dict__, 
            sort_keys=True,
            indent=4)

    def __str__(self):
        return self.__json__()

    def __repr__(self):
        return self.__json__()
    
    def __getitem__(self, key):
        for k in self.__dict__.keys():
            if k.lower() == key.lower():
                return self.__dict__[k]
        return self.__dict__[key]


class PackageVersion(PrintableObject):
    Id: str
    Package2: dict
    Name: str
    SubscriberPackageVersionId: str
    IsReleased: bool
    ReleaseVersion: str
    MajorVersion: int
    MinorVersion: int
    PatchVersion: int
    BuildNumber: int
    version: str

    def __init__(self, package2VersionRecord):
        rec = dict(package2VersionRecord)
        for key in package_query_fields:
            setattr(self, key, rec[key]) if key in rec.keys() else None
        self.version = f"{self.MajorVersion}.{self.MinorVersion}.{self.PatchVersion}"
        if self.BuildNumber is not None:
            self.version += f".{self.BuildNumber}"


class PackageDependencyIds(PrintableObject):
    subscriberPackageVersionIds: list[str]

    def __init__(self, deps):
        if "ids" in deps:
            self.subscriberPackageVersionIds = [x['subscriberPackageVersionId'] for x in deps["ids"]]


class SFDXPackageBase(PrintableObject):
    package_path: str = None
    package: str = None
    versionName: str = None
    versionNumber: str = None
    default: bool
    versionDescription = None
    postInstallURL = None
    ancestorId = None
    definitionFile = None

    def __init__(self, package):
        rec = dict(package)
        for key in rec.keys():
            setattr(self, key, rec[key])
            if key == "path":
                setattr(self, "package_path", rec[key])


class SFDXPackage(SFDXPackageBase):
    latestDeployedVersionNumber: str = None
    dependencies: list[SFDXPackageBase]

    def __init__(self, package):
        super().__init__(package)
        self.dependencies = []
        if "dependencies" in package.keys():
            self.dependencies = [SFDXPackageBase(x) for x in package["dependencies"]]

    def set_latest_deployed_version(self, version):
        if version is None:
            return
        if self.latestDeployedVersionNumber is None:
            self.latestDeployedVersionNumber = version
        else:
            if self.latestDeployedVersionNumber < version:
                self.latestDeployedVersionNumber = version


class PackageAlias(PrintableObject):
    package: str
    versionNumber: str = None
    subscriberPackageVersionId: str = None
    package2Id: str = None

    def __init__(self, key, val):
        self.package = key
        if val.startswith("04t"):
            self.subscriberPackageVersionId = val
        if val.startswith("0Ho"):
            self.package2Id = val
        if "@" in key:
            self.package = key.split("@")[0]
            self.versionNumber = key.split("@")[1]
            

class SFDXPackages(PrintableObject):

    packages: list[SFDXPackage] = []
    packageAliases = []

    def __init__(self, project_config):
        if project_config is None:
            raise ValueError("project_config is required")
        self.project_config = project_config
        sfdxConfig = self.project_config.sfdx_project_config
        packagesDirs = [SFDXPackage(x) for x in sfdxConfig["packageDirectories"]
                        if "package" in x.keys()]
        self.packages = packagesDirs
        if "packageAliases" in sfdxConfig.keys():
            self.packageAliases = []
            for key in sfdxConfig["packageAliases"].keys():
                self.packageAliases.append(PackageAlias(key, sfdxConfig["packageAliases"][key]))
            for alias in self.packageAliases:
                for package in self.packages:
                    if package.package == alias.package:
                        package.set_latest_deployed_version(alias.versionNumber)
                        package.subscriberPackageVersionId = alias.subscriberPackageVersionId
                        break
