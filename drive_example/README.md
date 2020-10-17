# `drive_example`

List your Google Drive root directory, or upload a file.

```shell
$ cargo run
# Lists all objects in your root folder of Drive.
...
$ cargo run -- ~/some_file.txt
# Uploads the given file to your root folder, and prints the involved File
# objects and the used request parameters.
...
```

