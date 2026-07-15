#!/usr/bin/env python

import argparse
import logging
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import transaction
from django.db.models import Count, Min

from care.emr.models.organization import Organization

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class GovtOrgDeduper:
    """Remove duplicate government organizations created by non-idempotent loads.

    Duplicates are identified by ``(parent_id, name)`` within the same
    ``level_cache`` among system-generated govt organizations. For each group of
    duplicates the row with the lowest ``id`` is kept as the canonical object and
    the rest are soft-deleted (``deleted=True``).

    Because deletion is soft (no cascade), every reference to a duplicate is first
    repointed to the canonical object: child organizations, ``root_org`` links,
    the ``parent_cache`` / ``managing_organizations`` arrays, and any foreign key
    from another model (patients, users, facilities, questionnaires, etc.).

    Levels are processed shallowest-first so that once a duplicate's children are
    repointed onto the canonical parent, the deeper level's dedup pass merges any
    resulting same-named siblings.
    """

    # Integer array fields on Organization that embed organization ids by value.
    ARRAY_ID_FIELDS = ("parent_cache", "managing_organizations")

    def __init__(self, apply_changes=False, hard_delete=False):
        self.apply_changes = apply_changes
        self.hard_delete = hard_delete
        self.references_repointed = 0
        self.base_qs = Organization.objects.filter(org_type="govt", system_generated=True)

    def find_duplicate_groups(self, level):
        return (
            self.base_qs.filter(level_cache=level)
            .values("parent_id", "name")
            .annotate(num=Count("id"), keep=Min("id"))
            .filter(num__gt=1)
        )

    def repoint_references(self, dup, keep):
        """Point every object referencing ``dup`` at ``keep`` instead.

        Returns the number of references updated (or that would be updated in
        dry-run mode).
        """
        updated = 0

        # Foreign keys from any model, including Organization's own self-relations
        # (`parent`, `root_org`).
        for relation in Organization._meta.related_objects:
            field_name = relation.field.name
            related_model = relation.related_model
            if relation.many_to_many:
                logger.warning(
                    "Skipping many-to-many relation %s.%s; repoint manually if needed",
                    related_model.__name__,
                    field_name,
                )
                continue
            referencing = related_model._default_manager.filter(**{field_name: dup})
            if self.apply_changes:
                updated += referencing.update(**{field_name: keep})
            else:
                updated += referencing.count()

        # Integer array fields on Organization that store ids by value.
        for field_name in self.ARRAY_ID_FIELDS:
            referencing = Organization._default_manager.filter(**{f"{field_name}__contains": [dup.id]})
            if self.apply_changes:
                for org in referencing:
                    values = getattr(org, field_name)
                    setattr(org, field_name, [keep.id if value == dup.id else value for value in values])
                    org.save(update_fields=[field_name])
                    updated += 1
            else:
                updated += referencing.count()

        return updated

    def dedupe_level(self, level):
        deleted_total = 0
        for group in self.find_duplicate_groups(level):
            keep = self.base_qs.get(id=group["keep"])
            duplicates = list(
                self.base_qs.filter(
                    level_cache=level,
                    parent_id=group["parent_id"],
                    name=group["name"],
                ).exclude(id=group["keep"])
            )

            logger.info(
                "level=%s parent=%s name='%s' → keeping id=%s, removing %s duplicate(s)",
                level,
                group["parent_id"],
                group["name"],
                group["keep"],
                len(duplicates),
            )

            for dup in duplicates:
                references = self.repoint_references(dup, keep)
                self.references_repointed += references
                logger.info(
                    "  %s id=%s → %s reference(s) repointed to id=%s",
                    "repointed" if self.apply_changes else "[DRY RUN] would repoint",
                    dup.id,
                    references,
                    keep.id,
                )
                if self.apply_changes:
                    if self.hard_delete:
                        Organization.objects.filter(pk=dup.pk).delete()
                    else:
                        dup.deleted = True
                        dup.save(update_fields=["deleted"])

            deleted_total += len(duplicates)
        return deleted_total

    def run(self):
        levels = sorted(self.base_qs.values_list("level_cache", flat=True).distinct())
        logger.info("Deduplicating govt organizations across levels: %s", levels)

        total = 0
        with transaction.atomic():
            for level in levels:
                total += self.dedupe_level(level)
            if not self.apply_changes:
                logger.info("[DRY RUN] no changes committed")

        delete_mode = "hard-delete" if self.hard_delete else "soft-delete"
        prefix = "" if self.apply_changes else f"[DRY RUN] would {delete_mode} "
        logger.info("%s%s duplicate organization(s)", prefix, total)
        repoint_prefix = "" if self.apply_changes else "[DRY RUN] would repoint "
        logger.info("%s%s reference(s) in total", repoint_prefix, self.references_repointed)


def main():
    parser = argparse.ArgumentParser(
        description="Remove duplicate government organizations (local bodies, wards, etc.) "
        "created by re-running the loader. Runs in dry-run mode unless --apply is passed."
    )
    parser.add_argument(
        "--apply",
        default=False,
        action="store_true",
        help="Actually delete duplicates. Without this flag the script only reports what it would do.",
    )
    parser.add_argument(
        "--hard",
        default=False,
        action="store_true",
        help="Permanently delete duplicates instead of soft-deleting (deleted=True).",
    )

    args = parser.parse_args()

    deduper = GovtOrgDeduper(apply_changes=args.apply, hard_delete=args.hard)
    deduper.run()


if __name__ == "__main__":
    main()
