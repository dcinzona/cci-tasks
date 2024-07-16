from logging import getLogger
from cumulusci.salesforce_api.org_schema import Schema, unzip_database
from cumulusci.tasks.salesforce import BaseSalesforceApiTask


class refreshDB(BaseSalesforceApiTask):
    def _run_task(self):
        org_config = self.org_config
        logger = self.org_config.logger or getLogger(__name__)
        with org_config.get_orginfo_cache_dir(Schema.__module__) as directory:
            # directory.mkdir(exist_ok=True, parents=True)
            schema_path = directory / "org_schema.db.gz"
            self.logger.info(f"schema path: {schema_path}")
            if schema_path.exists():
                try:
                    unzip_database(schema_path, "org_schema.db")
                except Exception as e:
                    logger.warning(
                        f"Cannot read `{schema_path}`. Recreating it. Reason `{e}`."
                    )
