# roxora-os.github.io

The Roxora website, served at https://roxora-os.github.io.

Download, Boards, Docs and the Raspberry Pi Imager repository file
(`os_list.json`) are generated from [roxora-os/build](https://github.com/roxora-os/build)
when the site is built: its releases, `boards.conf` and `docs/*.md`. The other
pages are fragments in `content/`. The workflow in `.github/workflows/site.yml`
builds and deploys on every push to `main` and every six hours.

## Building locally

    pip install -r tools/requirements.txt
    python3 tools/fetch_upstream.py
    python3 tools/build.py
    python3 tools/check_links.py
    python3 tools/os_list.py check _site/os_list.json
    cd _site && python3 -m http.server

To try the pages with release data before there is a release, use the sample
catalog from the build repository. That build is written to
`output/sample-site/`, never to `_site/`:

    python3 tools/fetch_upstream.py --sample path/to/sample-catalog.json
    python3 tools/build.py

The PatternFly CSS in `assets/patternfly/` is built by
`sh tools/patternfly/build.sh`, which needs node and npm. Add a component to
its list before using it in the markup.

The brand files in `assets/brand/` are copies from
[roxora-os/design](https://github.com/roxora-os/design). The wordmark font is
Space Grotesk Bold under the SIL Open Font License (`assets/fonts/`).

## License

GPL-2.0, see `LICENSE`.
