# `youtube_example`

List top 5 youtube videos.

```shell
$ cargo run
# Lists the videos.
```

Please note that you need a client secret to run this binary. Download it from
[Developer Console](https://console.developers.google.com) and place it into the
file `client_secret.json` in your working directory so that `youtube_example` can
find it.

Run with `RUST_LOG=debug` in order to see an accurate record of HTTP requests
being sent and received.
