from typing import Mapping
from cumulusci.tasks.bulkdata.step import DataOperationType
from cumulusci.tasks.bulkdata.mapping_parser import MappingStep

is_backup_patched = False


def init_overrides():

    global is_backup_patched
    if is_backup_patched:
        # import inspect
        # print(inspect.getsource(MappingStep._check_field_permission))
        return
    is_backup_patched = True
    print("\nApplying custom overrides\n")

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

    MappingStep._check_field_permission = custom_check_field_permission
