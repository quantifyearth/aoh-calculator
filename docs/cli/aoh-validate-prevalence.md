To run the model validation use this command:

{{ cli_help("aoh.validation.validate_map_prevalence", prog="aoh-validate-prevalence") }}


This will produce a CSV file listing just the AoH maps that fail model validation.

**Note:** The validation tools require R to be installed on your system with the `lme4` and `lmerTest` packages.
