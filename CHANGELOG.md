# 0.0.4 (2025-07-23)

## Bug fixes

- Add a `command_suite` to prevent error messagens when DataLad parses the extension.

## Changed

- The authentication realm was shortened.
  It now consists of the PublicnEUro dataset ID.


# 0.0.3 (2025-07-23)

## New features

- A first release of the PublicnEUro extension. It adds a URL handler for
  PublicnEUro datasets to DataLad. This allows using the new
  `uncurl-publicneuro`-special remote to add files from PublicnEUro datasets to
  a DataLad dataset via `git annex addurl`. See the [README](README.md) for
  usage instructions.
