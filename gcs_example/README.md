# `gcs_example`

For demonstrating/testing file uploads (a bit like `drive_example`, after all --
but the GCS API does some things differently than Drive).

## Usage

Uploads a file to a specified bucket. Expects a service account key in the
`client_secret.json` file. You can download it from the Cloud console, and it
should look roughly like this:

```json
{
  "type": "service_account",
  "project_id": "project",
  "private_key_id": "...key id...",
  "private_key": "...private key...",
  "client_email": "account@project.iam.gserviceaccount.com",
  "client_id": "106100510664759551719",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/account@project.iam.gserviceaccount.com"
}
```

You can then find out more by running

```bash
$ gcs_example --help
```
