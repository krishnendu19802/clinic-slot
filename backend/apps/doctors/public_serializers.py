from rest_framework import serializers


class SearchParamsSerializer(serializers.Serializer):
    speciality = serializers.SlugField(required=False)
    city = serializers.CharField(required=False)
    area = serializers.CharField(required=False)
    pincode = serializers.CharField(required=False)
    lat = serializers.FloatField(required=False, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=False, min_value=-180, max_value=180)
    date = serializers.DateField(required=False)
    available_today = serializers.BooleanField(required=False)
    fee_max = serializers.IntegerField(required=False, min_value=0)  # paise
    experience_min = serializers.IntegerField(required=False, min_value=0)
    gender = serializers.ChoiceField(choices=["male", "female", "other"], required=False)
    language = serializers.CharField(required=False)
    sort = serializers.ChoiceField(choices=["earliest", "distance", "experience", "fee"], default="earliest")
