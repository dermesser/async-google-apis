// A manual client for a Google API (e.g. Drive), to test what makes sense and what doesn't.

mod drive_v3_types;

use drive_v3_types as drive;

use yup_oauth2::InstalledFlowAuthenticator;
use std::string::String;
use std::str::FromStr;

use std::collections::HashMap;

use hyper::Uri;
use hyper_rustls::HttpsConnector;
use serde_json::Value;

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct AboutDriveThemes {
    #[serde(rename = "backgroundImageLink")]
    background_image_link: String,
    #[serde(rename = "colorRgb")]
    color_rgb: String,
    #[serde(rename = "id")]
    id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct AboutStorageQuota {
    // i64
    #[serde(rename = "limit")]
    limit: String,
    // i64
    #[serde(rename = "usage")]
    usage: String,
    // i64
    #[serde(rename = "usageInDrive")]
    usage_in_drive: String,
    // i64
    #[serde(rename = "usageInDriveTrash")]
    usage_in_drive_trash: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct AboutTeamDriveThemes {
    #[serde(rename = "backgroundImageLink")]
    background_image_link: String,
    #[serde(rename = "colorRgb")]
    color_rgb: String,
    #[serde(rename = "id")]
    id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct About {
    #[serde(rename = "appInstalled")]
    app_installed: bool,
    #[serde(rename = "canCreateDrives")]
    can_create_drives: bool,
    #[serde(rename = "canCreateTeamDrives")]
    can_create_team_drives: bool,
    #[serde(rename = "driveThemes")]
    drive_themes: Vec<AboutDriveThemes>,
    #[serde(rename = "exportFormats")]
    export_formats: HashMap<String,Vec<String>>,
    #[serde(rename = "folderColorPalette")]
    folder_color_palette: Vec<String>,
    #[serde(rename = "importFormats")]
    import_formats: HashMap<String,Vec<String>>,
    #[serde(rename = "kind")]
    kind: String,
    #[serde(rename = "maxImportSizes")]
    max_import_sizes: HashMap<String,String>,
    // i64
    #[serde(rename = "maxUploadSize")]
    max_upload_size: String,
    #[serde(rename = "storageQuota")]
    storage_quota: AboutStorageQuota,
    #[serde(rename = "teamDriveThemes")]
    team_drive_themes: Vec<AboutTeamDriveThemes>,
    #[serde(rename = "user")]
    user: User,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct User {
    #[serde(rename = "displayName")]
    display_name: String,
    #[serde(rename = "emailAddress")]
    email_address: String,
    #[serde(rename = "kind")]
    kind: String,
    #[serde(rename = "me")]
    me: bool,
    #[serde(rename = "permissionId")]
    permission_id: String,
    #[serde(rename = "photoLink")]
    photo_link: String,
}

type TlsConnr = HttpsConnector<hyper::client::HttpConnector>;
type TlsClient = hyper::Client<TlsConnr, hyper::Body>;

fn https_client() -> TlsClient {
    let conn = hyper_rustls::HttpsConnector::new();
    let cl = hyper::Client::builder().build(conn);
    cl
}

async fn get_about(cl: &mut TlsClient, auth: &mut yup_oauth2::authenticator::Authenticator<TlsConnr>) {
    let baseurl = "https://www.googleapis.com/drive/v3/";
    let path = "about";
    let tok = auth.token(&["https://www.googleapis.com/auth/drive.file"]).await.unwrap();
    let authtok = format!("?oauth_token={}&fields=*", tok.as_str());

    let resp = cl.get(Uri::from_str(&(String::from(baseurl)+path+&authtok)).unwrap()).await.unwrap();
    let body = resp.into_body();
    let body = hyper::body::to_bytes(body).await.unwrap();
    let dec = String::from_utf8(body.to_vec()).unwrap();
    let about: About = serde_json::from_str(&dec).unwrap();
    println!("{:?}", about);
}

#[tokio::main]
async fn main() {
    let sec = yup_oauth2::read_application_secret("client_secret.json")
        .await
        .expect("client secret couldn't be read.");

    let mut auth = InstalledFlowAuthenticator::builder(sec, yup_oauth2::InstalledFlowReturnMethod::HTTPRedirect)
        .persist_tokens_to_disk("tokencache.json")
        .build()
        .await
        .expect("installed flow authenticator!");

    let scopes = &["https://www.googleapis.com/auth/drive.file"];

    let mut cl = https_client();

    get_about(&mut cl, &mut auth).await;

    match auth.token(scopes).await {
        Ok(token) => println!("The token is {:?}", token),
        Err(e) => println!("error: {:?}", e),
    }
}
