"""
Core data models.
"""

import requests
import rapidjson
import pandas as pd
from functools import total_ordering
from typing import List, Any, Dict, Optional
from helpers import load_from_remote


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
        decisions: Optional[List["Decision"]] = None,
        advocates: Optional[List["Advocate"]] = None,
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

        self.decisions = decisions
        self.advocates = advocates
        self.heard_by = heard_by
        self.decided_by = decided_by
        self.transcripts = transcripts

    def get_transcript_df(self, groupby=True) -> pd.DataFrame:
        dfs = []
        if not self.decisions:
            return None
        for decision in self.decisions:
            if not decision.ballots:
                return None
            vote_df = pd.DataFrame(
                [({"voter": x.voter, "vote": x.vote}) for x in decision.ballots]
            )
            if not self.transcripts:
                joined_df = vote_df
                joined_df["text"] = ""
                joined_df.columns = ["speaker", "vote", "text"]
                dfs.append(joined_df[["speaker", "text", "vote"]])
            else:
                for transcript in self.transcripts:
                    speech_df = pd.DataFrame(
                        [
                            {"speaker": x.speaker, "text": x.text}
                            for x in transcript.utterances
                        ]
                    )
                    joined_df = speech_df.merge(
                        vote_df, left_on="speaker", right_on="voter"
                    )[["speaker", "text", "vote"]]
                    dfs.append(joined_df)
        df = pd.concat(dfs)
        df["term"] = self.term
        df["docket_number"] = self.docket_number
        if groupby:
            return (
                df.groupby(["speaker", "term", "docket_number"])
                .agg({"text": lambda x: " ".join(x), "vote": "first"})
                .reset_index()
            )
        else:
            return df[['speaker', 'term', 'docket_number', 'text', 'vote']]

    @classmethod
    def from_id(cls, term: int, docket_number: str, verbose: bool = True) -> "Case":
        url = f"https://api.oyez.org/cases/{term}/{docket_number}"
        data = load_from_remote(url, verbose=verbose)
        return cls.from_json(data, verbose)

    @classmethod
    def from_json(cls, data: Any, verbose: bool = True) -> "Case":
        if data["advocates"]:
            advocates = [Advocate.from_json(person) for person in data["advocates"]]
        else:
            advocates = None
        if data["oral_argument_audio"]:
            transcripts = [
                Transcript.from_id(argument["id"], verbose=verbose)
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

        if data["decisions"]:
            decisions = [
                Decision.from_json(
                    decision,
                    data["first_party"],
                    data["second_party"],
                    data["first_party_label"],
                    data["second_party_label"],
                )
                for decision in data["decisions"]
            ]
        else:
            decisions = None

        return cls(
            data["term"],
            data["docket_number"],
            data["ID"],
            data["first_party"],
            data["second_party"],
            data["description"],
            data["name"],
            decisions,
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
    def from_id(cls, id: int, verbose: bool = True) -> "Transcript":
        url = f"https://api.oyez.org/case_media/oral_argument_audio/{id}"
        data = load_from_remote(url, verbose=verbose)
        return cls.from_json(data)

    @classmethod
    def from_json(cls, data: Any) -> "Transcript":
        utterances = []
        for section in data["transcript"]["sections"]:
            for turn in section["turns"]:
                try:
                    spk = turn["speaker"]
                    speaker = Person(
                        spk["ID"], spk["name"], spk["last_name"], spk["identifier"]
                    )
                except Exception:
                    speaker = None
                text = " ".join([x["text"] for x in turn["text_blocks"]])
                utterance = Utterance(speaker, text, turn["start"], turn["stop"])
                utterances.append(utterance)
        return cls(data["id"], data["title"], utterances)


@total_ordering
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

    def __lt__(self, other) -> str:
        return self.name.lower() < other.name.lower()

    def __eq__(self, other) -> bool:
        """
        Assume two people are same if they have the same name.

        This is not guaranteed to work but is probably okay for analysis now.
        """
        if not other:
            return False
        return self.name == other.name

    def __hash__(self):
        return hash(repr(self))

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
        appointing_president: Optional[str],
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
        return f"https://api.oyez.org/preson_role/{self.role_type}/{self.role_id}"

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
    def __init__(
        self, speaker: Person, text: str, start: Optional[int], end: Optional[int]
    ) -> None:
        self.speaker = speaker
        self.text = text
        self.start = start
        self.end = end

    def __repr__(self) -> str:
        return f"{self.speaker} ({self.start} to {self.end}): '{self.text}'"


class Ballot:
    def __init__(self, voter: "Person", vote: str):
        self.voter = voter
        self.vote = vote

    def __repr__(self):
        return f"{self.voter} voted with the {self.vote}."

    @classmethod
    def from_json(cls, data: Any) -> "Ballot":
        voter = Justice.from_json(data["member"])
        vote = data["vote"]
        return cls(voter, vote)


class Decision:
    def __init__(
        self,
        ballots: Optional[List["Ballot"]],
        winning_party: str,
        decision_type: str,
        first_party: str,
        second_party: str,
        first_party_label: str,
        second_party_label: str,
        majority_vote: int,
        minority_vote: int,
    ):
        self.ballots = ballots
        self.decision_type = decision_type
        self.majority_vote = majority_vote
        self.minority_vote = minority_vote
        self.winning_party = None
        self.winning_party_name = winning_party
        if winning_party:
            if winning_party in first_party:
                self.winning_party = first_party_label
            elif winning_party in second_party:
                self.winning_party = second_party_label

    @classmethod
    def from_json(
        cls,
        data: Any,
        first_party: str,
        second_party: str,
        first_party_label: str,
        second_party_label: str,
    ) -> "Decision":
        ballots = None
        winning_party = None

        if data["votes"]:
            ballots = [Ballot.from_json(ballot) for ballot in data["votes"]]
        if data["winning_party"]:
            winning_party = data["winning_party"]

        return cls(
            ballots,
            winning_party,
            data["decision_type"],
            first_party,
            second_party,
            first_party_label,
            second_party_label,
            data["majority_vote"],
            data["minority_vote"],
        )

    def __repr__(self) -> str:
        return f"""{self.majority_vote} - {self.minority_vote} decision in favor of {self.winning_party} {self.winning_party_name}."""
