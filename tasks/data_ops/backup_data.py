
from pathlib import Path
import csv
import time
import typing as T
from tempfile import TemporaryDirectory

from cumulusci.core.datasets import _make_task  # , Dataset
from cumulusci.tasks.bulkdata.extract import ExtractData
from cumulusci.tasks.salesforce.SOQLQuery import SOQLQuery
from tasks.data_ops.generate_full_mapping import GenerateFullMapping
from cumulusci.tasks.sample_data.capture_sample_data import CaptureSampleData
from cumulusci.tasks.salesforce.BaseSalesforceApiTask import BaseSalesforceApiTask
from cumulusci.tasks.bulkdata.generate_mapping_utils.generate_mapping_from_declarations import (
    SimplifiedExtractDeclarationWithLookups,
    )
from cumulusci.core.exceptions import BulkDataException
from cumulusci.salesforce_api.org_schema import Filters, get_org_schema
from cumulusci.salesforce_api.filterable_objects import OPT_IN_ONLY, NOT_COUNTABLE  # , NOT_EXTRACTABLE
from cumulusci.tasks.bulkdata.extract_dataset_utils.extract_yml import (
    ExtractRulesFile,
    ExtractDeclaration
)
from cumulusci.tasks.bulkdata.mapping_parser import validate_and_inject_mapping
from cumulusci.tasks.bulkdata.step import DataOperationType
from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.salesforce_api.org_schema import Schema
from cumulusci.core.utils import process_bool_arg, process_list_arg

from cumulusci.tasks.bulkdata.step import DataOperationStatus, get_query_operation
from cumulusci.tasks.bulkdata.mapping_parser import MappingStep as CumulusciMappingStep
from cumulusci.tasks.bulkdata.mapping_parser import MappingSteps as CumulusciMappingSteps
from cumulusci.utils import log_progress
from typing import Mapping, Dict

import copy

capture_options = copy.deepcopy(CaptureSampleData.task_options)
capture_options["extraction_definition"]["required"] = True
generate_full_mapping_options = copy.deepcopy(GenerateFullMapping.task_options)
extract_data_options = copy.deepcopy(ExtractData.task_options)
extract_data_options["mapping"]["required"] = False  # this will be generated by capture
soql_query_options = copy.deepcopy(SOQLQuery.task_options)


class BackupData(BaseSalesforceApiTask):
    """
    Task to backup data from a Salesforce org to a local directory.
    Example: cci task run backup_data --dataset <folderName> --org <org_alias> --extraction-defition datasets/extract_accounts.yml
    """

    task_options = {
        "extraction_definition": {
            "description": "The path to the extraction definition file. File will be created if it does not exist",
            "required": False,
        },
        "dataset": {
            "description": "The name of the dataset to extract",
            "required": True,
        },
        "preview": {
            "description": "Preview the data extraction without writing to disk",
            "required": False,
        },
        "include_setup_data": {
            "description": "Include setup data like ApexClasses. Default is False",
            "required": False,
        },
        "sobjects": {
            "description": "A comma separated list of sobjects to extract.  Overrides the extraction definition and includes all fields",
            "required": False,
            },
        "populated_only": {
            "description": "Only include objects with data",
            "required": False,
        },
    }

    always_include_objects = ["User", "Group"]
    unix_time = int(time.time())

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        self.name = self.options.get("dataset", "default")
        self.preview = process_bool_arg(self.options.get("preview"))
        self.include_setup_data = process_bool_arg(self.options.get("include_setup_data"))
        self.sobjects = process_list_arg(self.options.get("sobjects"))
        self.root_dir = Path(self.project_config.repo_root or "")
        self.populated_only = process_bool_arg(self.options.get("populated_only"))
        self.extraction_definition = self.extract_file

    @property
    def path(self) -> Path:
        return self.root_dir / "datasets" / self.name
    
    @property
    def data_path(self) -> Path:
        return self.path / f"{self.unix_time}"

    @property
    def extract_file(self) -> Path:
        return self.path / f"{self.unix_time}-{self.name}.extract.yml"
    
    @property
    def mapping_file(self) -> Path:
        return self.path / f"{self.unix_time}" / f"_{self.unix_time}.mapping.yml"
    
    def _csv_path(self, sobject):
        return self.data_path / f"{sobject}.csv"

    def _run_task(self):
        if self.preview:
            with TemporaryDirectory() as tempdir:
                self.root_dir = Path(tempdir)
                self._run_exectute()
        else:
            self._run_exectute()
        list_todo(self.logger)

    def _run_exectute(self):

        extractable_data = self._get_extractable_objects()
        if self.include_setup_data:
            opt_in_only = []
        else:
            opt_in_only = [f["name"] for f in self.tooling.describe()["sobjects"] if f["name"] not in extractable_data]  # type: ignore
            opt_in_only += OPT_IN_ONLY + ["ScratchOrgInfo", "PromptError"]
        
        filters = [Filters.queryable]
        if self.populated_only:
            filters.append(Filters.populated)

        with get_org_schema(
            self.sf,
            self.org_config,
            include_counts=True,
            included_objects=extractable_data,
            filters=filters,
        ) as schema:
            if not self.data_path.exists():
                self.data_path.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Extracting data to {self.data_path}")
            self._build_decls_input()

            mappingDict = self.create_extract_mapping_file_from_declarations(
                list(self.decls.values()), schema, opt_in_only=opt_in_only
            )
            sobjectArray = list(mappingDict.keys())  # + self.always_include_objects
            self.logger.info(f"...Identified {len(sobjectArray)} objects to process")
            include = ",".join(list(set(sobjectArray)))
            ignore = ",".join(opt_in_only)

            self._build_mapping(include, ignore)

            if not self.preview:
                self.logger.info(f"\n...Extracting data for {len(self.mapping.keys())} objects...")
                for mapping in self.mapping.values():
                    sf_object = mapping["sf_object"]
                    self.logger.info(f"\nExtracting data for {sf_object}")
                    soql = self._soql_for_mapping(mapping)
                    self._run_query(soql, mapping)
            else:
                self._print_preview()

    def _build_decls_input(self):
        if self.sobjects:
            self.decls = {f"{sobject}": ExtractDeclaration(sf_object=sobject, fields=["FIELDS(ALL)"]) for sobject in self.sobjects}
        else:
            if user_provided_def := self.options.get("extraction_definition"):
                self.extraction_definition = Path(user_provided_def)
                if not self.extraction_definition.exists():
                    self.extraction_definition = self.extract_file

            self.logger.info(f"\n...Processing extraction definition: {self.extraction_definition}")
            self.decls = ExtractRulesFile.parse_extract(self.extraction_definition)
        return self.decls

    def _print_preview(self):
        self.logger.info("Preview mode enabled. No data will be extracted.\n")
        lb = "-" * 80
        lb = f"\n{lb}\n"
        decls = {k: {vk: vv for vk, vv in v if vk in ("sf_object", "fields")} for k, v in self.decls.items()}
        if self.sobjects:
            import yaml
            self.logger.info(f"\nExtraction Defenition:{lb}")
            self.logger.info(yaml.safe_dump(decls))
        else:
            self.logger.info(f"\nExtraction Defenition:{lb}{self.extraction_definition.read_text()}\n")
        self.logger.info(f"\nMapping YAML:{lb}{self.mapping_file.read_text()}")
        self.logger.info(f"\nSUMMARY{lb}")
        sorted_mapping = [f"{k['sf_object']} ({len(k['fields'])} {'Fields' if len(k['fields']) > 1 else 'Field'})" 
                          for k in self.mapping.values()]  
        sorted_mapping.sort()
        deli = "\n - "
        if len(self.mapping.keys()) < 20:
            self.logger.info(f"SObjects: {deli}{deli.join(sorted_mapping)}")
        else:
            self.logger.info(f"SObjects: {deli}{deli.join(sorted_mapping[:10])}\n... (output truncated){deli}{sorted_mapping[-1]}")
        self.logger.info(f"\nNumber of sObjects identified: {len(self.mapping.keys())}")

    def _build_mapping(self, include: str, ignore: str):
        self.logger.info("...Getting related objects and building mapping file for extract")
        mappingTask = _make_task(
            GenerateFullMapping, 
            project_config=self.project_config, 
            org_config=self.org_config,
            logger=self.logger,
            path=self.mapping_file,
            include=include,
            ignore=ignore,
            break_cycles="auto",
            )
        mappingTask()
        self.logger.info(f"Mapping saved to : {self.mapping_file}")
        self.mapping = MappingSteps.parse_from_yaml(self.mapping_file)

    def _get_extractable_objects(self):
        not_countable = NOT_COUNTABLE + ("NetworkUserHistoryRecent", "OutgoingEmail", "OutgoingEmailRelation")
        extractable_data = []

        if self.include_setup_data:
            sobjectList = [f for f in self.sf.describe()["sobjects"] 
                           if f["queryable"] is True
                           and f["createable"] is True
                           and f["keyPrefix"] is not None
                           and f["associateEntityType"] is None
                           and f["name"] not in not_countable
                           ]            
            extractable_data = [f["name"] for f in sobjectList]

        else:
            from tasks.data_ops.get_sobjects import GetSObjects
            task = _make_task(GetSObjects, project_config=self.project_config, org_config=self.org_config)
            extractable_data = task()
            extractable_data = [o for o in set(extractable_data + self.always_include_objects) if o not in not_countable]

        return extractable_data

    def _run_query(self, soql, mapping):
        """Execute a Bulk or REST API query job and store the results."""
        csvPath = self._csv_path(mapping['sf_object'])
        field_map = mapping.get_complete_field_map(include_id=True)
        columns = [field_map[f] for f in field_map]
        with open(csvPath, "w") as f:
            f.write(",".join(columns))
            f.write("\n")

        step = get_query_operation(
            sobject=mapping.sf_object,
            api=mapping.api,
            fields=list(mapping.get_extract_field_list()),
            api_options={},
            context=self,
            query=soql,
        )
        step.query()
        # self.logger.info(f"Querying {mapping['sf_object']} with SOQL: {soql}")

        if step.job_result.status is DataOperationStatus.SUCCESS:
            if step.job_result.records_processed:
                self.logger.info("Downloading and importing records")
                self._process_results(mapping, step, csvPath=csvPath)
            else:
                self.logger.info(f"No records found for sObject {mapping['sf_object']}")
        else:
            raise BulkDataException(
                f"Unable to execute query: {','.join(step.job_result.job_errors)}"
            )

    def _process_results(self, mapping, step, csvPath):
        """Process the results of a query and write them to a CSV file."""
        record_iterator = log_progress(step.get_results(), self.logger)
        writer = csv.writer(open(csvPath, "a"), quoting=csv.QUOTE_ALL)
        for row in record_iterator:
            writer.writerow(row)
        
    def _soql_for_mapping(self, mapping):
        """Return a SOQL query suitable for extracting data for this mapping."""
        sf_object = mapping.sf_object
        fields = mapping.get_extract_field_list()
        soql = f"SELECT {', '.join(fields)} FROM {sf_object}"

        if mapping.record_type:
            soql += f" WHERE RecordType.DeveloperName = '{mapping.record_type}'"

        if mapping.soql_filter is not None:
            soql = self.append_filter_clause(
                soql=soql, filter_clause=mapping.soql_filter
            )

        return soql

    def create_extract_mapping_file_from_declarations(
        self,
        decls: T.List[ExtractDeclaration], 
        schema: Schema, 
        opt_in_only: T.Sequence[str]
    ):
        """Create a mapping file sufficient for driving an extract process
        from an extract declarations file."""
        assert decls is not None
        
        from cumulusci.tasks.bulkdata.generate_mapping_utils.generate_mapping_from_declarations import (
            classify_and_filter_lookups
        )
        from tasks.data_ops.extract_dataset_utils.synthesize_extract_declarations import (
            flatten_declarations,
            )
        
        simplified_decls = flatten_declarations(decls, schema, opt_in_only)
        # self.logger.info(f"Flattened Declarations: {simplified_decls}")
        simplified_decls = classify_and_filter_lookups(simplified_decls, schema)
        mappings = [self._mapping_decl_for_extract_decl(decl) for decl in simplified_decls]
        return dict(pair for pair in mappings if pair)

    def _mapping_decl_for_extract_decl(
        self,
        decl: SimplifiedExtractDeclarationWithLookups,
    ):
        """Make a CCI extract mapping step from a SimplifiedExtractDeclarationWithLookups"""
        lookups = {lookup: {"table": tables} for lookup, tables in decl.lookups.items()}
        mapping_dict: dict[str, T.Any] = {
            "sf_object": decl.sf_object,
        }
        if decl.where:
            mapping_dict["soql_filter"] = decl.where
        if decl.api:
            mapping_dict["api"] = decl.api.value
        mapping_dict["fields"] = decl.fields
        if lookups:
            mapping_dict["lookups"] = lookups

        return (decl.sf_object, mapping_dict)


class MappingStep(CumulusciMappingStep):

    def _check_field_permission(
        self, describe: Mapping, field: str, operation: DataOperationType
    ):
        perms = ("queryable",)
        # Fields don't have "queryable" permission.
        return field in describe and all(
            # To discuss: is this different than `describe[field].get(perm, True)`
            describe[field].get(perm) if perm in describe[field] else True
            for perm in perms
        )


class MappingSteps(CumulusciMappingSteps):
    __root__: Dict[str, MappingStep]


class ExtractBackup(ExtractData):

    task_options = extract_data_options

    def _run_task(self):
        self._init_mapping()
        with self._init_db():
            for mapping in self.mapping.values():
                soql = self._soql_for_mapping(mapping)
                self._run_query(soql, mapping)

            self._map_autopks()

            if self.options.get("sql_path"):
                self._sqlite_dump()

    def _init_mapping(self):
        """Load a YAML mapping file."""
        mapping_file_path = self.options["mapping"]
        if not mapping_file_path:
            raise TaskOptionsError("Mapping file path required")
        self.logger.info(f"Mapping file: {self.options['mapping']}")

        self.mapping = MappingSteps.parse_from_yaml(mapping_file_path)

        validate_and_inject_mapping(
            mapping=self.mapping,
            sf=self.sf,
            namespace=self.project_config.project__package__namespace,
            data_operation=DataOperationType.QUERY,
            inject_namespaces=self.options["inject_namespaces"],
            drop_missing=self.options["drop_missing_schema"],
            org_has_person_accounts_enabled=self.org_config.is_person_accounts_enabled,
        )
    
    def _map_autopks(self):
        # Convert Salesforce Ids to autopks
        for m in self.mapping.values():
            lookup_keys = list(m.lookups.keys())
            if not m.get_oid_as_pk():
                if lookup_keys:
                    self._convert_lookups_to_id(m, lookup_keys)


def list_todo(logger):

    todolist = [
        "Make dependency graph also include child objects",
        "Add database support",
        "Add support for PK encryption of extracted data"
        ]
    
    lb = "-" * 80
    lb = f"\n{lb}\n"
    deli = "\n - "

    logger.info(f"{lb}TODO:{lb} - {deli.join(todolist)}")
