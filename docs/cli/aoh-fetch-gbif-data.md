This command fetches occurrence data from [GBIF](https://gbif.org) to do occurrence checking as per Dahal et al.

Important notes:

1. You will need a GBIF account for this.
2. This can take a long time, particularly for birds as there are so many records.
3. It can also generate a lot of data, hundreds of gigabytes worth, so ensure you have enough storage space!

{{ cli_help("aoh.validation.fetch_gbif_data", prog="aoh-fetch-gbif-data") }}
