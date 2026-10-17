from tools.country_probe import interesting_driver_fields


def test_country_probe_extracts_country_club_and_license_fields():
    fields = interesting_driver_fields(
        {
            "UserName": "T.J. Lee",
            "Country": "USA",
            "CountryCode": "US",
            "ClubName": "Ohio",
            "DivisionName": "Division 2",
            "LicString": "A 4.99",
            "CarNumber": "34",
        }
    )

    assert fields == {
        "ClubName": "Ohio",
        "Country": "USA",
        "CountryCode": "US",
        "DivisionName": "Division 2",
        "LicString": "A 4.99",
    }
