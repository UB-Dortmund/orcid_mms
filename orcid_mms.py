# The MIT License
#
#  Copyright 2016-2017 UB Dortmund <daten.ub@tu-dortmund.de>.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#  THE SOFTWARE.

import babelfish
import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
import datetime
import requests
import simplejson as json
import uuid

try:
    import local_secrets as secrets
except ImportError:
    import secrets


ORCID_PUBTYPES = {
    'Monograph': 'BOOK',
    'AudioBook': 'BOOK',
    'Chapter': 'BOOK_CHAPTER',
    'ChapterInLegalCommentary': 'BOOK_CHAPTER',
    'ChapterInMonograph': 'BOOK_CHAPTER',
    'review': 'BOOK_REVIEW',
    'Thesis': 'DISSERTATION',
    'Conference': 'CONFERENCE_PAPER',
    'Collection': 'EDITED_BOOK',
    'ArticleJournal': 'JOURNAL_ARTICLE',
    'SpecialIssue': 'JOURNAL_ISSUE',
    'InternetDocument': 'ONLINE_RESOURCE',
    'ArticleNewspaper': 'NEWSPAPER_ARTICLE',
    'Report': 'REPORT',
    'ResearchData': 'DATA_SET',
    'Patent': 'PATENT',
    'Lecture': 'LECTURE_SPEECH',
    'Standard': 'STANDARDS_AND_POLICY'
}

WTF_PUBTYPES = {
    'OTHER': 'Other',
    'REPORT': 'Report',
    'JOURNAL_ARTICLE': 'ArticleJournal',
    'DATA_SET': 'ResearchData',
    'DISSERTATION': 'Thesis',
    'EDITED_BOOK': 'Collection',
    'BOOK_CHAPTER': 'Chapter'
}

BIBTEX_PUBTYPES = {
    'Monograph': 'book',
    'AudioBook': 'book',
    'Chapter': 'inbook',
    'ChapterInLegalCommentary': 'inbook',
    'ChapterInMonograph': 'inbook',
    'review': 'misc',
    'Thesis': 'phdthesis',
    'Conference': 'proceedings',
    'Collection': 'book',
    'ArticleJournal': 'article',
    'SpecialIssue': 'misc',
    'InternetDocument': 'misc',
    'ArticleNewspaper': 'article',
    'Report': 'unpublished',
    'ResearchData': 'misc',
    'Patent': 'misc',
    'Lecture': 'misc',
    'Standard': 'misc'
}


def orcid2mms(orcid_id='', orcid_work_record=None):

    mms_json = {}

    if orcid_work_record and (orcid_work_record.get('visibility') == 'PUBLIC' or orcid_work_record.get('visibility') == 'LIMITED'):
        mms_json['id'] = str(uuid.uuid4())

        orcid_sync = {
            'orcid_id': orcid_id,
            'orcid_put_code': '',
            'orcid_visibility': str(orcid_work_record.get('visibility'))
        }
        mms_json['orcid_sync'] = [orcid_sync]
        for extid in orcid_work_record.get('external-ids').get('external-id'):
            if extid.get('external-id-type') == 'doi':
                # print('\tadd scopus_id "%s"' % extid.get('external-id-value'))
                mms_json['DOI'] = [extid.get('external-id-value')]
            if extid.get('external-id-type') == 'eid':
                # print('\tadd scopus_id "%s"' % extid.get('external-id-value'))
                mms_json['scopus_id'] = extid.get('external-id-value')
            if extid.get('external-id-type') == 'wosuid':
                # print('\tadd wosuid "%s"' % extid.get('external-id-value'))
                mms_json['WOSID'] = extid.get('external-id-value').replace('WOS:', '')
            if extid.get('external-id-type') == 'pmid':
                # print('\tadd pmid "%s"' % extid.get('external-id-value'))
                mms_json['PMID'] = extid.get('external-id-value')
            if extid.get('external-id-type') == 'urn':
                # print('\tadd pmid "%s"' % extid.get('external-id-value'))
                mms_json['uri'] = [extid.get('external-id-value')]

        mms_json['title'] = orcid_work_record.get('title').get('title').get('value')
        if orcid_work_record.get('title').get('subtitle'):
            mms_json['subtitle'] = orcid_work_record.get('title').get('subtitle').get('value')

        mms_json['pubtype'] = WTF_PUBTYPES.get(orcid_work_record.get('type'))
        if not mms_json['pubtype']:
            WTF_PUBTYPES.get('OTHER')

        issued = orcid_work_record.get('publication-date').get('year').get('value')
        if orcid_work_record.get('publication-date').get('month'):
            issued += '-%s' % orcid_work_record.get('publication-date').get('month').get('value')
            if orcid_work_record.get('publication-date').get('day'):
                issued += '-%s' % orcid_work_record.get('publication-date').get('day').get('value')
        mms_json['issued'] = issued

        mms_json['editorial_status'] = 'new'
        mms_json['note'] = 'added by ORCID synchronization'
        mms_json['created'] = timestamp()
        mms_json['changed'] = timestamp()
        mms_json['owner'] = ['daten.ub@tu-dortmund.de']

    return mms_json


def mms2orcid(affiliation='', mms_records=None):
    orcid_records = []

    # logging.info('wtf_records: %s' % wtf_records)
    if mms_records is None:
        mms_records = []

    if len(mms_records) > 0:
        for record in mms_records:

            orcid_record = {}
            db = BibDatabase()
            db.entries = []
            bibtex_entry = {}

            # work type
            orcid_type = ORCID_PUBTYPES.get(record.get('pubtype'))
            if orcid_type is None:
                orcid_type = 'OTHER'
            orcid_record.setdefault('type', orcid_type)

            bibtex_type = BIBTEX_PUBTYPES.get(record.get('pubtype'))
            if bibtex_type is None:
                bibtex_type = 'misc'
            bibtex_entry.setdefault('ENTRYTYPE', bibtex_type)

            external_ids = {}
            external_id = []
            # ids - record id (source-work-id)
            ext_id = {}
            ext_id.setdefault('external-id-type', 'source-work-id')
            ext_id.setdefault('external-id-value', record.get('id'))
            ext_id.setdefault('external-id-relationship', 'SELF')
            if affiliation and affiliation in secrets.AFFILIATION_URL.keys():
                ext_id.setdefault('external-id-url', '%s%s/%s' % (secrets.AFFILIATION_URL.get(affiliation), record.get('pubtype'), record.get('id')))
            external_id.append(ext_id)
            bibtex_entry.setdefault('ID', record.get('id'))

            # ids - ISBN (isbn)
            if record.get('ISBN'):
                for isbn in record.get('ISBN'):
                    if isbn:
                        ext_id = {}
                        ext_id.setdefault('external-id-type', 'isbn')
                        ext_id.setdefault('external-id-value', isbn)
                        ext_id.setdefault('external-id-relationship', 'SELF')
                        external_id.append(ext_id)

            # ids - ISSN (issn)
            if record.get('ISSN'):
                for issn in record.get('ISSN'):
                    if issn:
                        ext_id = {}
                        ext_id.setdefault('external-id-type', 'issn')
                        ext_id.setdefault('external-id-value', issn)
                        ext_id.setdefault('external-id-relationship', 'SELF')
                        external_id.append(ext_id)

            # ids - ZDB (other-id)
            if record.get('ZDBID'):
                for zdbid in record.get('ZDBID'):
                    if zdbid:
                        ext_id = {}
                        ext_id.setdefault('external-id-type', 'other-id')
                        ext_id.setdefault('external-id-value', zdbid)
                        ext_id.setdefault('external-id-url', 'http://ld.zdb-services.de/resource/%s' % zdbid)
                        ext_id.setdefault('external-id-relationship', 'SELF')
                        external_id.append(ext_id)

            # ids - PMID (pmc)
            if record.get('PMID'):
                ext_id = {}
                ext_id.setdefault('external-id-type', 'pmid')
                ext_id.setdefault('external-id-value', record.get('PMID'))
                ext_id.setdefault('external-id-url', 'http://www.ncbi.nlm.nih.gov/pubmed/%s' % record.get('PMID'))
                ext_id.setdefault('external-id-relationship', 'SELF')
                external_id.append(ext_id)

            # ids - WOS-ID (wosuid)
            if record.get('WOSID'):
                ext_id = {}
                ext_id.setdefault('external-id-type', 'doi')
                ext_id.setdefault('external-id-value', record.get('WOSID'))
                ext_id.setdefault('external-id-url', 'http://ws.isiknowledge.com/cps/openurl/service?url_ver=Z39.88-2004&rft_id=info:ut/%s' % record.get('WOSID'))
                ext_id.setdefault('external-id-relationship', 'SELF')
                external_id.append(ext_id)

            # ids - doi
            if record.get('DOI'):
                for doi in record.get('DOI'):
                    if doi:
                        ext_id = {}
                        ext_id.setdefault('external-id-type', 'doi')
                        ext_id.setdefault('external-id-value', doi)
                        ext_id.setdefault('external-id-url', 'https://doi.org/%s' % doi)
                        ext_id.setdefault('external-id-relationship', 'SELF')
                        external_id.append(ext_id)
                bibtex_entry.setdefault('doi', record.get('DOI')[0])

            if external_id:
                external_ids.setdefault('external-id', external_id)

            orcid_record.setdefault('external-ids', external_ids)

            # titles
            title = {}
            title.setdefault('title', record.get('title'))
            if record.get('subtitle'):
                title.setdefault('subtitle', record.get('subtitle'))
            orcid_record.setdefault('title', title)

            title = record.get('title')
            if record.get('subtitle'):
                title += ': %s' % record.get('subtitle')
            bibtex_entry.setdefault('title', title)

            # issued
            if record.get('issued'):
                publication_date = {}
                date_parts = []
                for date_part in str(record.get('issued')).replace('[', '').replace(']', '').split('-'):
                    date_parts.append(date_part)
                publication_date.setdefault('year', int(date_parts[0]))
                bibtex_entry.setdefault('year', date_parts[0])
                if len(date_parts) > 1:
                    publication_date.setdefault('month', int(date_parts[1]))
                    bibtex_entry.setdefault('month', date_parts[1])
                if len(date_parts) > 2:
                    publication_date.setdefault('day', int(date_parts[2]))
                    bibtex_entry.setdefault('day', date_parts[2])
                orcid_record.setdefault('publication-date', publication_date)

            # contributors
            contributors = {}
            contributor = []
            author_str = ''
            for author in record.get('person'):
                if 'aut' in author.get('role'):
                    con = {}
                    con.setdefault('credit-name', author.get('name'))
                    if author.get('orcid'):
                        con.setdefault('contributor-orcid', {'uri': 'http://orcid.org/%s' % author.get('orcid')})
                    contributor_attributes = {}
                    contributor_attributes.setdefault('contributor-role', 'AUTHOR')
                    con.setdefault('contributor-attributes', contributor_attributes)
                    contributor.append(con)
                    if author_str != '':
                        author_str += ' and '
                    author_str += author.get('name')
            contributors.setdefault('contributor', contributor)
            orcid_record.setdefault('contributors', contributors)

            bibtex_entry.setdefault('author', author_str)

            # language
            if record.get('language') and record.get('language')[0] and record.get('language')[0] != 'None':
                lang_code = ''
                try:
                    lang_code = str(babelfish.Language.fromalpha3b(record.get('language')[0]))
                except babelfish.exceptions.LanguageReverseError:
                    pass
                if lang_code:
                    orcid_record.setdefault('language-code', lang_code)

            # is_part_of
            hosts = []
            if record.get('is_part_of'):
                hosts = record.get('is_part_of')

            for host in hosts:
                if host.get('is_part_of') != '':
                    try:
                        response = requests.get('%s/%s/%s' % (secrets.MMS_API, 'work',
                                                              host.get('is_part_of')),
                                                headers={'Accept': 'application/json'},
                                                )
                        status = response.status_code
                        if status == 200:
                            myjson = json.loads(response.content.decode('utf8').get('wtf_json'))

                            title = myjson.get('title')
                            if myjson.get('subtitle'):
                                title += ': %s' % myjson.get('subtitle')
                            orcid_record.setdefault('journal-title', title)
                            if bibtex_entry.get('ENTRYTYPE') == 'article':
                                bibtex_entry.setdefault('journal', title)
                            elif bibtex_entry.get('ENTRYTYPE') == 'inbook':
                                bibtex_entry.setdefault('booktitle', title)
                            elif bibtex_entry.get('ENTRYTYPE') == 'inproceedings':
                                bibtex_entry.setdefault('booktitle', title)
                            elif bibtex_entry.get('ENTRYTYPE') == 'incollection':
                                bibtex_entry.setdefault('booktitle', title)
                            else:
                                bibtex_entry.setdefault('series', title)
                    except AttributeError as e:
                        print('ERROR: ' % e)
                elif host.get('host_title'):
                    orcid_record.setdefault('journal-title', host.get('host_title'))

                if host.get('volume') != '':
                    bibtex_entry.setdefault('volume', host.get('volume'))
                else:
                    bibtex_entry.setdefault('volume', '')

            if bibtex_entry:
                db.entries.append(bibtex_entry)

            citation = {}
            citation.setdefault('citation-type', 'BIBTEX')
            citation.setdefault('citation-value', bibtexparser.dumps(db))
            orcid_record.setdefault('citation', citation)

            orcid_records.append(orcid_record)

    return orcid_records


def timestamp():
    date_string = str(datetime.datetime.now())[:-3]
    if date_string.endswith('0'):
        date_string = '%s1' % date_string[:-1]

    return date_string
