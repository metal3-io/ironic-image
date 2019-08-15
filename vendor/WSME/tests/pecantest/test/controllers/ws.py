# encoding=utf8
from pecan.rest import RestController

from wsme.types import Base, text, wsattr

import wsme
import wsmeext.pecan

import six


class Author(Base):
    id = int
    firstname = text
    books = wsattr(['Book'])

    @staticmethod
    def validate(author):
        if author.firstname == 'Robert':
            raise wsme.exc.ClientSideError("I don't like this author!")
        return author


class Book(Base):
    id = int
    name = text
    author = wsattr('Author')


class BookNotFound(Exception):
    message = "Book with ID={id} Not Found"
    code = 404

    def __init__(self, id):
        message = self.message.format(id=id)
        super(BookNotFound, self).__init__(message)


class NonHttpException(Exception):
    message = "Internal Exception for Book ID={id}"
    code = 684

    def __init__(self, id):
        message = self.message.format(id=id)
        super(NonHttpException, self).__init__(message)


class BooksController(RestController):

    @wsmeext.pecan.wsexpose(Book, int, int)
    def get(self, author_id, id):
        book = Book(
            name=u"Les Confessions d’un révolutionnaire pour servir à "
                 u"l’histoire de la révolution de février",
            author=Author(lastname=u"Proudhon")
        )
        return book

    @wsmeext.pecan.wsexpose(Book, int, int, body=Book)
    def put(self, author_id, id, book=None):
        book.id = id
        book.author = Author(id=author_id)
        return book


class Criterion(Base):
    op = text
    attrname = text
    value = text


class AuthorsController(RestController):

    _custom_actions = {
        'json_only': ['GET'],
        'xml_only': ['GET']
    }

    books = BooksController()

    @wsmeext.pecan.wsexpose([Author], [six.text_type], [Criterion])
    def get_all(self, q=None, r=None):
        if q:
            return [
                Author(id=i, firstname=value)
                for i, value in enumerate(q)
            ]
        if r:
            return [
                Author(id=i, firstname=c.value)
                for i, c in enumerate(r)
            ]
        return [
            Author(id=1, firstname=u'FirstName')
        ]

    @wsmeext.pecan.wsexpose(Author, int)
    def get(self, id):
        if id == 999:
            raise wsme.exc.ClientSideError('Wrong ID')

        if id == 998:
            raise BookNotFound(id)

        if id == 997:
            raise NonHttpException(id)

        if id == 996:
            raise wsme.exc.ClientSideError('Disabled ID', status_code=403)

        if id == 911:
            return wsme.api.Response(Author(),
                                     status_code=401)
        if id == 912:
            return wsme.api.Response(None, status_code=204)

        if id == 913:
            return wsme.api.Response('foo', status_code=200, return_type=text)

        author = Author()
        author.id = id
        author.firstname = u"aname"
        author.books = [
            Book(
                name=u"Les Confessions d’un révolutionnaire pour servir à "
                     u"l’histoire de la révolution de février",
            )
        ]
        return author

    @wsmeext.pecan.wsexpose(Author, body=Author, status_code=201)
    def post(self, author):
        author.id = 10
        return author

    @wsmeext.pecan.wsexpose(None, int)
    def delete(self, author_id):
        print("Deleting", author_id)

    @wsmeext.pecan.wsexpose(Book, int, body=Author)
    def put(self, author_id, author=None):
        return author

    @wsmeext.pecan.wsexpose([Author], rest_content_types=('json',))
    def json_only(self):
        return [Author(id=1, firstname=u"aname", books=[])]

    @wsmeext.pecan.wsexpose([Author], rest_content_types=('xml',))
    def xml_only(self):
        return [Author(id=1, firstname=u"aname", books=[])]
