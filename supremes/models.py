"""
Core data models.
"""

from typing import List, Any, Dict, Optional
import requests
import rapidjson


class Case:
    def __init__(
        self,
        term: int,
        docket_number: int,
        id: int,
        first_party: str,
        second_party: str,
        description: str,
        name: str,
        advocates: List["Advocate"],
        heard_by: Optional[List["Court"]] = None,
        decided_by: Optional[List["Court"]] = None,
        transcripts: Optional[List["Transcript"]] = None,
    ) -> None:
        self.term = term
        self.docket_number = docket_number
        self.id = id
        self.first_party = first_party
        self.second_party = second_party
        self.description = description
        self.name = name

        self.advocates = advocates
        self.heard_by = heard_by
        self.decided_by = decided_by
        self.transcripts = transcripts

    @classmethod
    def from_id(cls, term: int, docket_number: str) -> "Case":
        url = f"https://api.oyez.org/cases/{term}/{docket_number}"
        data = rapidjson.loads(requests.get(url).content)
        return cls.from_json(data)

    @classmethod
    def from_json(cls, data: Any) -> "Case":
        advocates = [Advocate.from_json(person) for person in data["advocates"]]
        if data["oral_argument_audio"]:
            transcripts = [
                Transcript.from_id(argument["id"])
                for argument in data["oral_argument_audio"]
            ]
        else:
            transcripts = None

        if data["decided_by"]:
            decided_by_courts = [Court.from_json(court) for court in data["decided_by"]]
        else:
            decided_by_courts = None

        if data["heard_by"]:
            heard_by_courts = [Court.from_json(court) for court in data["heard_by"]]
        else:
            heard_by_courts = None

        return cls(
            data["term"],
            data["docket_number"],
            data["ID"],
            data["first_party"],
            data["second_party"],
            data["description"],
            data["name"],
            advocates,
            heard_by_courts,
            decided_by_courts,
            transcripts,
        )

    def __repr__(self) -> str:
        return f"{self.docket_number}: {self.name}"


class Transcript:
    def __init__(
        self, id: int, title: str, utterances: Optional[List["Utterance"]]
    ) -> None:
        self.id = id
        self.title = title
        self.utterances = utterances

    def __repr__(self) -> str:
        return self.title

    def get_transcript_url(self) -> str:
        return f"https://api.oyez.org/case_media/oral_argument_audio/{self.id}"

    @classmethod
    def from_id(cls, id: int) -> "Transcript":
        url = f"https://api.oyez.org/case_media/oral_argument_audio/{id}"
        data = rapidjson.loads(requests.get(url).content)
        return cls.from_json(data)

    @classmethod
    def from_json(cls, data: Any) -> "Transcript":
        utterances = []
        for section in data["transcript"]["sections"]:
            for turn in section["turns"]:
                spk = turn["speaker"]
                speaker = Person(
                    spk["ID"], spk["name"], spk["last_name"], spk["identifier"]
                )
                text = " ".join([x["text"] for x in turn["text_blocks"]])
                utterance = Utterance(speaker, text)
                utterances.append(utterance)
        return cls(data["id"], data["title"], utterances)


class Person:
    def __init__(self, id: int, name: str, last_name: str, identifier: str) -> None:
        self.id = id
        self.name = name
        self.last_name = last_name
        self.identifier = identifier

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name

    def get_person_url(self) -> str:
        return f"https://api.oyez.org/people/{self.identifier}"

    @classmethod
    def from_json(cls, data: Any) -> None:
        return cls(data["ID"], data["name"], data["last_name"], data["identifier"])


class Advocate(Person):
    def __init__(
        self,
        id: int,
        name: str,
        last_name: str,
        identifier: str,
        case_advocate_id: int,
        description: str,
    ) -> None:
        Person.__init__(self, id, name, last_name, identifier)
        self.case_advocate_id = case_advocate_id
        self.description = description

    def get_advocate_url(self):
        return (
            f"https://api.oyez.org/case_advocate/case_advocate/{self.case_advocate_id}"
        )

    @classmethod
    def from_json(cls, data: Any) -> "Advocate":
        adv_id = data["href"].split("/")[-1]

        return cls(
            data["advocate"]["ID"],
            data["advocate"]["name"],
            data["advocate"]["last_name"],
            data["advocate"]["identifier"],
            adv_id,
            data["advocate_description"],
        )


class Justice(Person):
    def __init__(
        self, id: int, name: str, last_name: str, identifier: str, roles: List["Role"]
    ) -> None:
        Person.__init__(self, id, name, last_name, identifier)
        self.roles = roles

    @classmethod
    def from_json(cls, data: Any) -> "Justice":
        roles = [Role.from_json(role) for role in data["roles"]]
        return cls(
            data["ID"], data["name"], data["last_name"], data["identifier"], roles
        )


class Court:
    def __init__(
        self, id: int, identifier: str, name: str, justices: List["Justice"]
    ) -> None:
        self.id = id
        self.identifier = identifier
        self.name = name
        self.justices = justices

    @classmethod
    def from_json(cls, data: Any) -> "Court":
        if type(data) == str:
            return None
        if data:
            justices = [Justice.from_json(justice) for justice in data["members"]]
            return cls(data["ID"], data["identifier"], data["name"], justices)
        return None

    def __repr__(self) -> str:
        return self.name


class Role:
    def __init__(
        self,
        role_id: int,
        role_title: int,
        role_type: str,
        appointing_president: str,
        institution_name: str,
        date_end: int,
        date_start: int,
    ) -> None:
        self.role_id = role_id
        self.role_title = role_title
        self.role_type = role_type
        self.appointing_president = appointing_president
        self.institution_name = institution_name
        self.date_end = date_end
        self.date_start = date_start

    def __repr__(self):
        return self.role_title

    def get_role_url(self):
        return f"https://api.oyez.org/preson_role/{self.role_type}/{self.id}"

    @classmethod
    def from_json(cls, data: Any) -> "Role":
        id = data["href"].split("/")[:-1]
        return cls(
            id,
            data["role_title"],
            data["type"],
            data["appointing_president"],
            data["institution_name"],
            data["date_end"],
            data["date_start"],
        )


class Utterance:
    def __init__(self, speaker: Person, text: str) -> None:
        self.speaker = speaker
        self.text = text

    def __repr__(self) -> str:
        return f"{self.speaker}: '{self.text}'"

