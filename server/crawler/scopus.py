"""
API key: https://dev.elsevier.com/apikey/manage

API methods: https://dev.elsevier.com/scopus.html

Listing with all documentation: https://dev.elsevier.com/technical_documentation.html:
* Possible searches: https://dev.elsevier.com/tecdoc_search_request.html
* Author queries: https://dev.elsevier.com/tips/AuthorSearchTips.htm
* Possible retrieval: https://dev.elsevier.com/tecdoc_retrieval_request.html
* Cited-by: https://dev.elsevier.com/tecdoc_cited_by_in_scopus.html

Potential URLs for scraping:
* https://www.scopus.com/author/document/retrieval.uri?authorId=123456&tabSelected=citedLi
* https://www.scopus.com/results/citedbyresults.uri?src=s&citedAuthorId=123456&sot=cite

Short example on scraping:
    # As soon as `scopusSessionUUID` is missing from the cookie, it will fail subsequent times
    # `SCSessionID` can be missing and then brought back and it will still work, though.
    # But otherwise both cookies are to be present.
    print(requests.get(url, headers={
        #'Host': 'www.scopus.com',
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0',
        #'Accept': '*/*',
        #'Accept-Language': 'en-US,en;q=0.5',
        #'Accept-Encoding': 'gzip, deflate, br',
        #'Referer': 'https://www.scopus.com/authid/detail.uri?authorId=123456',
        #'X-NewRelic-ID': 'VQQPUFdVCRADVVVXAwABVA==',
        #'X-Requested-With': 'XMLHttpRequest',
        #'Connection': 'keep-alive',
        #'Cookie': '__cfduid=d81739ecd4ba566fcf62f0636d94e21681582450322; scopusSessionUUID=e6fefb15-309b-4a07-9; scopus.machineID=0BB20A9430BEF5B211C3DA071F3D18FD.wsnAw8kcdt7IPYLO0V48gA; xmlHttpRequest=true; NEW_CARS_COOKIE=00730078006B0075004E00380069004A0061006E00660038004B00740079003900570065006300770076007700520051006300380077004C00670077005500670074004300410043004B0075004D003000590030004B00350059006300560057002B0079005000300052003200420032004D006A00410062002B006B006A00360059002B006F00480035002F006D0066004F005A0046004C0070006400460075006F004600530050006F004F00440068003500630059003600380039004C00660044003200310049007A006300380065006600770031007800420050002F00340048006400620041003200440074007500520043004C0039005800420061004B; NEW_homeAcc_cookie=0045004F006E00720071005500380073006E004A006E004A0052007400580032007200550043004C006C0032003100530032006B0036002F00680055007100630058006E0043004F0043006E0044006B0052004B00670062002B004800450063005800660044007600610077003D003D; SCSessionID=83D7925F12E4CEBC3ECA18ABCDC13865.wsnAw8kcdt7IPYLO0V48gA; javaScript=true; screenInfo="768:1366"; __cfruid=8f58e135626099c2979d17014b88107562fed5d1-1583141930; NEW_AE_SESSION_COOKIE=1583142129302',
        'Cookie': 'scopusSessionUUID=26577281-788b-4633-b; SCSessionID=78B7A5D39829AFF91076C9019120A238.wsnAw8kcdt7IPYLO0V48gA',
        #'TE': 'Trailers'
    }).text)
"""
class Scopus:
    def __init__(self, session, api_key, base_url='https://api.elsevier.com'):
        self._session = session
        self._headers = {
            'X-ELS-APIKey': api_key,
            'Accept': 'application/json'
        }
        self._base_url = base_url

    async def search_author(self, query, limit=None):
        """
        Author Search.

        Description: https://dev.elsevier.com/documentation/AuthorSearchAPI.wadl

        Query: https://dev.elsevier.com/tips/AuthorSearchTips.htm

        Return: https://dev.elsevier.com/guides/AuthorSearchViews.htm

        Note:
            This does not search author details, for that make
            a request to `prism:url`.
        """
        response = (await self.request(
            f'{self._base_url}/content/search/author', query=query))['search-results']

        got = len(response['entry'])
        for x in response['entry']:
            yield x

        if limit is None:
            limit = int(response['opensearch:totalResults'])

        while got < limit:
            url = next((x['@href'] for x in response['link'] if x['@ref'] == 'next'), None)
            if url is None:
                break

            response = (await self.request(url))['search-results']
            got += len(response['entry'])
            for x in response['entry']:
                yield x

    async def get_author(self, *, eid=None, author_id=None, orcid=None):
        """
        Author Retrieval.

        Description: https://api.elsevier.com/content/author

        Query: Only one of: `eid`, `author_id`, `orcid`; should be present.

        Return: https://dev.elsevier.com/guides/AuthorRetrievalViews.htm

        Note:
            The API claims all valid views are: LIGHT, STANDARD, ENHANCED,
            METRICS, DOCUMENTS, ENTITLED, ORCID, ORCID_BIO and ORCID_WORKS.

            However, it seems like the following don't work: DOCUMENTS,
            ORCID, ORCID_BIO and ORCID_WORKS

            In addition, ENTITLED is only for checking if we can access
            the resource.
        """
        # assert only one is present
        assert sum(x is not None for x in (eid, author_id, orcid)) == 1

        if eid:
            return (await self.request(
                f'{self._base_url}/content/author', eid=eid, view='ENHANCED'))['author-retrieval-response'][0]
        elif author_id:
            return (await self.request(
                f'{self._base_url}/content/author', author_id=author_id, view='ENHANCED'))['author-retrieval-response'][0]
        elif orcid:
            # Undocumented in the common endpoint, but works
            return (await self.request(
                f'{self._base_url}/content/author', orcid=orcid, view='ENHANCED'))['author-retrieval-response'][0]
        else:
            raise RuntimeError('impossible case reached')

    async def search_scopus(self, query):
        """
        Description: https://dev.elsevier.com/documentation/ScopusSearchAPI.wadl

        Query: https://dev.elsevier.com/tips/ScopusSearchTips.htm

        Return: https://dev.elsevier.com/guides/ScopusSearchViews.htm

        Examples: https://kitchingroup.cheme.cmu.edu/blog/2015/04/03/Getting-data-from-the-Scopus-API/
        """
        # TODO PLAY MORE WITH THIS SEEMS PROMISING
        return (await self.request(
            f'{self._base_url}/content/search/scopus', query=query, view='COMPLETE'))

    async def citation(self):
        """
        Citation Overview.

        Description: https://dev.elsevier.com/documentation/AbstractCitationAPI.wadl
        """
        # Seems to 403 forbidden: https://github.com/ElsevierDev/elsapy/issues/7
        return (await self.request(
            f'{self._base_url}/content/abstract/citations'))

    async def citation_count(self):
        """
        Abstract Citations Count.

        Description: https://dev.elsevier.com/documentation/AbstractCitationCountAPI.wadl
        """
        # Seems to 403 forbidden: https://github.com/ElsevierDev/elsapy/issues/7
        return (await self.request(
            f'{self._base_url}/content/abstract/citation-count'))

    async def request(self, url, **params):
        print(url)
        async with self._session.get(url, params=params, headers=self._headers) as resp:
            if resp.status == 200:
                return (await resp.json())
            else:
                raise ValueError(f'HTTP {resp.status} fetching {url}:\n{await resp.text()}')

"""
EXTRA

3 Retrieve info for a document
url = ("http://api.elsevier.com/content/abstract/scopus_id/"
        + SCOPUS_ID
        + "?field=authors,title,publicationName,volume,issueIdentifier,"
        + "prism:pageRange,coverDate,article-number,doi,citedby-count,prism:aggregationType")

4 Get information for all documents
url = ("http://api.elsevier.com/content/abstract/scopus_id/"
          + SCOPUS_ID
          + "?field=authors,title,publicationName,volume,issueIdentifier,"
          + "prism:pageRange,coverDate,article-number,doi,citedby-count,prism:aggregationType")
"""