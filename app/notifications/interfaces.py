from abc import ABC, abstractmethod


class EmailSenderInterface(ABC):

    @abstractmethod
    def send_activation_email(self, email: str, activation_link: str) -> None:
        pass

    @abstractmethod
    def send_password_reset_email(self, email: str, reset_link: str) -> None:
        pass

    @abstractmethod
    def send_password_change(self, email: str) -> None:
        pass

    @abstractmethod
    def send_remove_movie(self, email: str, movie_name: str, cart_id: int) -> None:
        pass

    @abstractmethod
    def send_comment_answer(self, email: str, answer_text: str) -> None:
        pass
    