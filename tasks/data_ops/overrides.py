from typing import Mapping
from cumulusci.tasks.bulkdata.step import DataOperationType
import cumulusci.tasks.bulkdata.mapping_parser
from tasks.data_ops.filterable_objects import (
    OPT_IN_ONLY,
    NOT_COUNTABLE,
    NOT_EXTRACTABLE,
)

is_backup_patched = False


def init_overrides():

    global is_backup_patched
    if is_backup_patched:
        # import inspect
        # print(inspect.getsource(MappingStep._check_field_permission))
        return
    is_backup_patched = True
    # print(" >>> Applying custom overrides <<< \n")

    def custom_check_field_permission(
        self, describe: Mapping, field: str, operation: DataOperationType
    ):
        perms = ("queryable",)
        self.logger.info(f"Checking field {field} for operation {operation}")
        exit(1)
        # Fields don't have "queryable" permission.
        return field in describe and all(
            # To discuss: is this different than `describe[field].get(perm, True)`
            describe[field].get(perm) if perm in describe[field] else True
            for perm in perms
        )

    cumulusci.tasks.bulkdata.mapping_parser.MappingStep._check_field_permission = (
        custom_check_field_permission
    )
    
    cumulusci.salesforce_api.filterable_objects.OPT_IN_ONLY = OPT_IN_ONLY
    cumulusci.salesforce_api.filterable_objects.NOT_COUNTABLE = NOT_COUNTABLE
    cumulusci.salesforce_api.filterable_objects.NOT_EXTRACTABLE = NOT_EXTRACTABLE

    return ' >>> Custom overrides applied <<< \n'
