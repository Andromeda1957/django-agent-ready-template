# Host Maintenance Runbook

Use for routine Ubuntu package maintenance on the production host. This is
separate from application deployment and never performs an unattended Ubuntu
release upgrade.

## Schedule

Set repository variable `ENABLE_HOST_MAINTENANCE=true` only after production SSH
secrets and app variables are verified. The workflow then runs weekly. It
installs security-update support, applies normal package upgrades, reboots only
when required, and verifies the application, Nginx, package state, and failed
unit list.

## Release Upgrades

`apt upgrade` or `apt dist-upgrade` updates packages within the installed Ubuntu
release; it is not an OS release migration. Moving between Ubuntu releases needs
a separate owner-reviewed plan with verified backups, compatibility checks, a
maintenance window, rollback/rebuild procedure, and post-upgrade validation.

## Completion

The maintenance run is complete only when the workflow is green and application
service, Nginx, `dpkg --audit`, reboot state, and failed units have all been
checked after updates.
