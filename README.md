# cci-tasks

Custom python tasks for CumulusCI

## Development

To work on this project in a scratch org:

1. [Set up CumulusCI](https://cumulusci.readthedocs.io/en/latest/tutorial.html)
2. Run `cci flow run dev_org --org dev` to deploy this project.
3. Run `cci org browser dev` to open the org in your browser.

## Tasks

### `backup_data`

_TODO:_

[ ] Add support for PK encryption of extracted data <br>
[ ] Add database support

This task will take a backup of data based on an extract declaration file. The declaration file is a yaml file that contains the object name and the fields to extract. 

**Command Syntax**: `cci task run backup_data --org <org_name> --dataset <dataset_name>`

#### Options:
- `--org` (Required) - The name of the org to run the task against
- `--extraction-definition` (Optional) - The path to the extraction definition file. If not provided, the task will create one for Account
- `--preview` (Optional) - If provided, the task will only print the mapping definition generated by the extraction definition
- `--include_setup_data` (Optional) - If provided, the task will include setup data in the backup, like ApexClass, ApexTestResult, etc.
- `--sobjects` (Optional) - A comma separated list of sobjects to extract.  Overrides the extraction definition and includes all fields
- `--populated_only` (Optional) - Only include objects with data.
- `--include-children` (Optional) - Include child objects in the backup.  This will extract all fields for any objects that reference 
objects in the extraction definition or passed in via options.  Ignored groupings like OBJECTS(ALL).

#### Extraction Definition File
The extraction definition file accepts sObject API Names, Field API Names, and  groups like:
- `OBJECTS(ALL)` to extract all objects
- `OBJECTS(CUSTOM)` to extract all custom objects
- `OBJECTS(STANDARD)` to extract all standard objects
- `FIELDS( ALL | CUSTOM | STANDARD )` to extract fields matching the criteria

Depenting on the criteria, the task will identify dependencies and extract the related objects and fields. Manually defined objects and fields will always be extracted.
```yaml
# Example extraction definition file
extract:
    Account:
        fields: FIELDS(ALL) # Extract all fields on Account
    OBJECTS(CUSTOM): # Extract all custom objects with the defined fields below
        fields:
            - Id
            - Name
            - CreatedDate
            - LastModifiedDate
            - FIELDS(CUSTOM) # Extract all custom fields on the custom objects
```

#### `--sobjects` option

This will extract all fields for the specified sobjects (standard and custom). It will also identify dependencies and extract related objects and fields. This option overrides the extraction definition file.

This hasn't been *thoroughly* tested, so please use with caution.


### `update_help_text`

This task will check your local project directory for any object fields that have `<inlineHelpText>` defined in the metadata. If it exists, it will compare that with what is currently in the org and update the org if necessary.

**Command Syntax**: `cci task run update_help_text --org <org_name>`

#### Options:
- `--org` (Required) - The name of the org to run the task against
- `--dir` (Optional) - The directory to search for metadata files. Defaults to the current directory