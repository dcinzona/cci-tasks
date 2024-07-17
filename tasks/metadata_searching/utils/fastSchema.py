from cumulusci.cli.runtime import CliRuntime
from cumulusci.salesforce_api.org_schema import Schema, unzip_database
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlalchemy import create_engine
from logging import getLogger
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
from cumulusci.tasks.bulkdata.generate_mapping import GenerateMapping
from utils.timer import timer
import os


class fastSchema:

    def __init__(self) -> None:
        self.logger = getLogger(__name__)
        self.pt = timer()
        runtime = CliRuntime(load_keychain=True)
        self.project_config = runtime.project_config
    
    def printTime(self, str='Total Time: '):
        self.pt.log(str)

    @contextmanager
    def get_local_schema(self, org_config):
        self.org_config = org_config
        self.sf = get_simple_salesforce_connection(self.project_config, org_config)
        self.logger = org_config.logger
        self.logger.info('Getting local copy of schema...')
        taskName = 'generate_dataset_mapping'
        taskCommand = f"cci task run {taskName} --org {org_config.name}"
        with org_config.get_orginfo_cache_dir(Schema.__module__) as directory:
            self.logger.info(f"Schema cache directory: '{os.path.abspath(directory)}'")
            directory.mkdir(exist_ok=True, parents=True)
            schema_path = directory / "org_schema.db.gz"
            if not schema_path.exists():
                self.logger.error(f"\n\nNo local schema found, please run: \n{taskCommand}")
                self.logger.info("...Attempting to refresh local cache: `{}`\n\n".format(taskCommand))
                task = GenerateMapping(self.project_config, self.project_config.get_task(taskName), org_config=org_config, name=taskName)
                task.sf = self.sf
                task._run_task()                

            with ExitStack() as closer:
                tempdir = TemporaryDirectory()
                closer.enter_context(tempdir)
                tempfile = Path(tempdir.name) / "temp_org_schema.db"
                schema = None
                if schema_path.exists():
                    try:
                        cleanups_on_failure = []
                        unzip_database(schema_path, tempfile)
                        cleanups_on_failure.extend([schema_path.unlink, tempfile.unlink])
                        engine = create_engine(f"sqlite:///{str(tempfile)}")

                        schema = Schema(engine, schema_path)
                        cleanups_on_failure.append(schema.close)
                        closer.callback(schema.close)
                        assert schema.sobjects.first().name
                        schema.from_cache = True
                        schema.block_writing()
                    except Exception as e:
                        self.logger.error(e)
                        schema = None
                        for cleanup_action in reversed(cleanups_on_failure):
                            cleanup_action()
                yield schema

    '''
    result can be processed using list(result)
    '''
    def query_Schema(self, org_schema, sql: str):
        try:
            result = org_schema.session.execute(sql)    
            return result    
        except Exception as e:
            print(e)
        return []

    def _init_api(self, base_url=None):
        rv = get_simple_salesforce_connection(
            self.project_config,
            self.org_config,
            api_version=None,
            base_url=base_url,
        )

        return rv
