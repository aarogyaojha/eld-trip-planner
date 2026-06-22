import csv
import io
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from trips.models import City

class Command(BaseCommand):
    help = 'Loads Simplemaps World Cities Basic dataset from local CSV'

    def handle(self, *args, **options):
        csv_path = os.path.join(settings.BASE_DIR, 'worldcities.csv')
        self.stdout.write(f"Reading from {csv_path}...")
        
        with open(csv_path, 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            
            self.stdout.write("Deleting old cities...")
            City.objects.all().delete()

            cities = []
            self.stdout.write("Parsing CSV...")
            for row in csv_reader:
                pop_str = row.get('population', '')
                population = int(float(pop_str)) if pop_str else None
                
                city = City(
                    name=row.get('city_ascii', row.get('city', '')),
                    state_name=row.get('admin_name', ''),
                    country_name=row.get('country', ''),
                    lat=float(row.get('lat', 0)),
                    lng=float(row.get('lng', 0)),
                    population=population
                )
                cities.append(city)
            
            self.stdout.write(f"Bulk creating {len(cities)} cities...")
            City.objects.bulk_create(cities, batch_size=5000)
            
        self.stdout.write(self.style.SUCCESS(f"Successfully loaded {len(cities)} cities!"))
