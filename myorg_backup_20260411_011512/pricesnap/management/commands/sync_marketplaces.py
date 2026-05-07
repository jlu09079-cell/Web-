from django.core.management.base import BaseCommand, CommandError

from pricesnap.sync import sync_marketplace_query


class Command(BaseCommand):
    help = "Fetch marketplace products for a search query and sync them into the database."

    def add_arguments(self, parser):
        parser.add_argument("query", type=str)
        parser.add_argument("--count", type=int, default=10)

    def handle(self, *args, **options):
        query = options["query"].strip()
        if not query:
            raise CommandError("Query cannot be empty.")

        synced, notes = sync_marketplace_query(query, result_count=options["count"])
        self.stdout.write(self.style.SUCCESS(f"Synced {synced} offers for query: {query}"))
        for note in notes:
            self.stdout.write(f"- {note}")
