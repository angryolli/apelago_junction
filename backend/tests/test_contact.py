from app.research.contact import PublishedAddress, addresses_in, choose_contact


def test_addresses_skip_files_trackers_and_placeholders() -> None:
    html = """
    <a href="mailto:hanna@sireness.fi">Hanna</a>
    <img src="apelagologo_blue_RGB@5x-1024x156.png">
    <p>firstname.lastname@norsepower.com</p>
    <p>605a7baede844d278b89dc95ae0a9123@sentry.io</p>
    """

    emails = [item.email for item in addresses_in(html)]

    assert emails == ["hanna@sireness.fi"]


def test_choose_prefers_the_named_person() -> None:
    addresses = [
        PublishedAddress(email="info@awake.ai"),
        PublishedAddress(email="karno.tenovuo@awake.ai"),
    ]

    chosen = choose_contact(
        addresses,
        "https://www.awake.ai",
        "BlueInvest names Karno Tenovuo as CEO.",
    )

    assert chosen.email == "karno.tenovuo@awake.ai"


def test_choose_uses_the_company_inbox_when_no_person_matches() -> None:
    addresses = [
        PublishedAddress(email="0037@procountor.apix.fi"),
        PublishedAddress(email="info@originbyocean.com"),
        PublishedAddress(email="ari.stjerna@originbyocean.com"),
    ]

    chosen = choose_contact(
        addresses,
        "https://www.originbyocean.com/",
        "Mari Granström",
    )

    assert chosen.email == "info@originbyocean.com"


def test_choose_prefers_a_named_leader_over_other_staff() -> None:
    html = "Contact us Mika Seppälä CEO mika@wesi.fi Antti Forsman Advisor antti@wesi.fi"
    addresses = addresses_in(html)

    chosen = choose_contact(addresses, "https://wesi.fi/", "")

    assert chosen.email == "mika@wesi.fi"
    assert chosen.name == "Mika Seppälä"
    assert chosen.role == "CEO"


def test_address_text_is_not_treated_as_a_person() -> None:
    html = "Registered office FI-00180 Helsinki contact@norsepower.com"

    addresses = addresses_in(html)

    assert addresses[0].email == "contact@norsepower.com"
    assert addresses[0].name == ""


def test_choose_keeps_a_single_company_address() -> None:
    addresses = [PublishedAddress(email="newkelpies@kelp.blue")] * 3

    chosen = choose_contact(addresses, "https://kelp.blue/global/about", "Caroline Slootweg")

    assert chosen.email == "newkelpies@kelp.blue"


def test_choose_ignores_partner_domains() -> None:
    addresses = [
        PublishedAddress(email="sales@partner.example"),
        PublishedAddress(email="contact@norsepower.com"),
    ]

    chosen = choose_contact(addresses, "https://www.norsepower.com/", "")

    assert chosen.email == "contact@norsepower.com"
