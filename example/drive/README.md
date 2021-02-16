# `Google Drive Example`

List your Google Drive root directory, or upload a file.

## `Usage`

```shell
CURRENT_DIR=`pwd`

# Generate Drive APIs
cd "$CURRENT_DIR/../../generate"
./generate.py --apis=drive:v3

# Add missing Media enum variant
cd "$CURRENT_DIR/../../"
git apply example/drive/media_download.patch

# Update cargo repo
cargo update

# Lists all objects in your root folder of Drive.
cargo run

# Uploads the given file to your root folder, and prints the involved File
# objects and the used request parameters.
cargo run -- ~/some_file.txt
```

Please note that you need a client secret to run this binary. Download it from
[Developer Console](https://console.developers.google.com) and place it into the
file `client_secret.json` in your working directory so that `drive` can
find it.

Run with `RUST_LOG=debug` in order to see an accurate record of HTTP requests
being sent and received.
