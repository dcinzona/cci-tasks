# discovered by trial and error. Usually extended with a list of
# tooling objects. i.e. any object which is both a tooling object
# and also a "regular" sobject will be skipped.
OPT_IN_ONLY = [
    "ActionLinkGroupTemplate",
    "ApexClass",
    "ApexTrigger",
    "AppAnalyticsQueryRequest",
    "AuraDefinition",
    "FeedItem",
    "Translation",
    "WebLinkLocalization",
    "RecordTypeLocalization",
    "ApexPage",
    "ApexTestQueueItem",
    "ApexTestResult",
    "ApexComponent",
    "ApexEmailNotification",
    "ApexTestResultLimits",
    "ApexTestRunResult",
    "ApexTestSuite",
    "AppMenuItem",
    "AuthProvider",
    "BrandTemplate",
    "OauthCustomScope",
    "OauthCustomScopeApp",
    "OauthTokenExchHandlerApp",
    "OauthTokenExchangeHandler",
]

NOT_COUNTABLE = (
    "ContentDocumentLink",  # ContentDocumentLink requires a filter by a single Id on ContentDocumentId or LinkedEntityId
    "ContentFolderItem",  # Implementation restriction: ContentFolderItem requires a filter by Id or ParentContentFolderId
    "ContentFolder",  # Similar to above
    "ContentFolderLink",  # Similar to above
    "ContentFolderMember",  # Similar to above
    "IdeaComment",  # you must filter using the following syntax: CommunityId = [single ID],
    "Vote",  # you must filter using the following syntax: ParentId = [single ID],
    "RecordActionHistory",  # Gack: 1133111327-118855 (1126216936)
    "DashboardSnapshotResults",  # Gack: 1198622208-46932 (1126216936)
    "RecordRecommendation",  # Implementation restriction: RecordRecommendation requires a filter on TargetSobjectType or TargetId or RecordRecommendationId
)

NOT_EXTRACTABLE = NOT_COUNTABLE + (
    "%__e",
    "%__mdt",
    "%__b",
    "%__x",
    "%__kav",
    "%__voteStat",
    "%__viewStat",
    "%__xo",  # Salesforce-to-Salesforce (S2S) spoke/proxy object
    "%__dlm",
    "%_hd",  # Historical Data'
    "%__chn",
    "%__p",
    "%ChangeEvent",
    "%Share",
    "%Access",
    "%History",
    "%Permission",
    "%PermissionSet",
    "%Permissions",
    "AuthorizationFormDataUse",
    "CustomHelpMenuSection",
    "DataUseLegalBasis",
    "DataUsePurpose",
    "ExternalDataUserAuth",
    "FieldPermissions",
    "FieldServiceMobileSettings",
    # "Group",
    # "GroupMember",
    "MacroInstruction",
    "NetworkUserHistoryRecent",
    "ObjectPermissions",
    "OutgoingEmail",
    "OutgoingEmailRelation",
    "PermissionSet",
    "PermissionSetAssignment",
    "PermissionSetGroup",
    "PermissionSetGroupComponent",
    "PermissionSetLicenseAssign",
    "PermissionSetTabSetting",
    # "Profile",
    # "RecordType",
    # "User",
    "UserAppInfo",
    "UserAppMenuCustomization",
    "UserCustomBadge",
    "UserCustomBadgeLocalization",
    "UserEmailPreferredPerson",
    "UserListView",
    "UserListViewCriterion",
    "UserPackageLicense",
    "UserPreference",
    "UserProvAccount",
    "UserProvAccountStaging",
    "UserProvMockTarget",
    "UserProvisioningConfig",
    "UserProvisioningLog",
    "UserProvisioningRequest",
    # "UserRole",
)


def pattern_match_single(objname: str, pattern: str):
    if pattern.startswith("%") and len(pattern) > 1:
        pat = pattern.lower().replace("%", "")
        if objname.endswith(pat):
            return objname.endswith(pat)
    else:
        return objname == pattern.lower()


def pattern_match(obj, patterns=NOT_EXTRACTABLE):
    objname = obj if isinstance(obj, str) else obj["name"]
    assert objname is not None, f"Object is not a dictionary or string: {obj}"
    objname = objname.lower()

    for pattern in patterns:
        if pattern_match_single(objname, pattern):
            return True
    return False


def sobject_is_valid(obj, patterns=NOT_EXTRACTABLE):
    found = pattern_match(obj, patterns)
    # if found:
    #     print(f"Skipping {obj if isinstance(obj, str) else obj['name']}")
    return not found


def filter_objects_by_pattern(objects: list, patterns=NOT_EXTRACTABLE):
    """Filter out objects that are not extractable"""
    return [f for f in objects if not pattern_match(f, patterns)]


def check_dictobject_filter(obj: dict, filters):
    return all([obj.get(f, False) for f in filters if f in obj])


# Generated with these patterns:
#     "%permission%",
#     "%use%",
#     "%access%",
#     "group",
#     "%share",
#     "NetworkUserHistoryRecent",
#     "ObjectPermissions",
#     "OmniSupervisorConfigUser",
# )

# And this code:
#
# patterns_to_ignore = NOT_EXTRACTABLE_WITHOUT_NOT_COUNTABLE

# names = [obj["name"] for obj in sf.describe()["sobjects"] if obj["createable"]]

# regexps_to_ignore = [
#     re.compile(pat.replace("%", ".*"), re.IGNORECASE) for pat in patterns_to_ignore
# ]

# for name in names:
#     if any(reg.match(name) for reg in regexps_to_ignore) and not ("__" in name):
#         print(name)
