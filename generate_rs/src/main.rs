mod discovery_v1_types;
mod schema;

use anyhow::{Error, Result};
use clap::{App, Arg, SubCommand};

enum ApiSource {
    /// API ID to fetch
    ApiId(String),
    /// URL of document to fetch
    ApiDoc(String),
}

struct RunConfig {
    api: ApiSource,
    discovery_base: String,
}

fn argparse() -> Result<RunConfig> {
    let app = App::new("generate_rs")
        .about("Generate asynchronous Rust stubs for Google REST APIs")
        .arg(
            Arg::with_name("api")
                .long("api")
                .value_name("API-ID")
                .help("Google API ID, e.g. drive:v3 or discovery:v1."),
        )
        .arg(
            Arg::with_name("discovery_base")
                .long("discovery_base")
                .value_name("DISCOVERY-BASE")
                .help("Base URL of Discovery service"),
        )
        .arg(
            Arg::with_name("doc_url")
                .long("doc_url")
                .value_name("DOC-URL")
                .help("URL of Discovery document to process directly (instead of --api)"),
        );
    let matches = app.get_matches();

    let api = match (matches.value_of("api"), matches.value_of("doc_url")) {
        (Some(id), None) => ApiSource::ApiId(id.into()),
        (None, Some(url)) => ApiSource::ApiDoc(url.into()),
        (None, None) => return Err(anyhow::anyhow!("Please specify either --api or --doc_url")),
        (Some(_), Some(_)) => {
            return Err(anyhow::anyhow!("Please specify either --api or --doc_url"))
        }
    };

    let discovery_base = matches
        .value_of("discovery_base")
        .unwrap_or("https://www.googleapis.com/discovery/v1/apis")
        .into();
    Ok(RunConfig {
        api: api,
        discovery_base: discovery_base,
    })
}

async fn fetch_doc_by_api_id(
    base_url: &str,
    id: &str,
) -> Result<discovery_v1_types::RestDescription> {
    let list: discovery_v1_types::DirectoryList = fetch_url(base_url).await?;

    if let Some(items) = list.items {
        if let Some(found) = items
            .iter()
            .find(|it| it.id.as_ref().map(|s| s.as_str()).unwrap_or("") == id)
        {
            let url = found.discovery_rest_url.clone().unwrap();
            return fetch_doc_by_url(url.as_str()).await;
        }
    }
    Err(anyhow::anyhow!("No API with this ID could be found"))
}

async fn fetch_doc_by_url(doc_url: &str) -> Result<discovery_v1_types::RestDescription> {
    fetch_url(doc_url).await
}

async fn fetch_url<Out: serde::de::DeserializeOwned>(url: &str) -> Result<Out> {
    let doc = reqwest::get(url).await?.text().await?;
    serde_json::from_reader(doc.as_bytes()).map_err(|e| anyhow::anyhow!(format!("Error parsing response '{}': {}", doc, e)))
}

#[tokio::main]
async fn main() {
    let cfg = argparse().unwrap();

    let doc = match cfg.api {
        ApiSource::ApiDoc(url) => fetch_doc_by_url(url.as_str()).await.unwrap(),
        ApiSource::ApiId(id) => fetch_doc_by_api_id(cfg.discovery_base.as_str(), id.as_str())
            .await
            .unwrap(),
    };
    println!("{:?}", doc);
}
