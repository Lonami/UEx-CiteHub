"""
API keys: https://msr-apis.portal.azure-api.net/
API methods: https://msr-apis.portal.azure-api.net/Products/project-academic-knowledge
Tutorial and attributes: https://docs.microsoft.com/en-us/azure/cognitive-services/academic-knowledge/queryexpressionsyntax

Website: https://academic.microsoft.com/home
"""
def new_filtered_dict(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}


class Academics:
    def __init__(self, session, api_key, base_url='https://api.labs.cognitive.microsoft.com/academic/v1.0/'):
        self._session = session
        self._headers = {
            'Ocp-Apim-Subscription-Key': api_key,
            'Accept': 'application/json'
        }
        self._base_url = base_url

    async def evaluate(
            self,
            expr: str,
            *,
            model: str = None,
            count: int = None,
            offset: int = None,
            orderby: str = None,
            attributes: str = None
    ):
        """
        Parameters
            expr
                A query expression that specifies which entities should be returned.

                For details, see
                https://docs.microsoft.com/en-us/academic-services/project-academic-knowledge/reference-query-expression-syntax.

                Query expressions should be in lowercase with no special characters.

                Single value:       Field='query'
                Exact single value: Field=='query'
                Prefix value:       Field='value'...
                Range:              Field>=3 (or) Field=[2010, 2012)
                Date:               Field='2020-02-20'
                And/or queries:     And(Or(Field='a', Field='b'), Field='c')
                Composite fields:   Composite(Comp.Field='a')

                Examples

                    Composite(AA.AuN='mike smith')

            model
                Name of the model that you wish to query. Currently, the value defaults to "latest".

            count
                Number of results to return.

            offset
                Index of the first result to return.

            orderby
                Name of an attribute that is used for sorting the entities. Optionally,
                ascending/descending can be specified. The format is: `name:asc` or `name:desc`.

            attributes
                A comma delimited list that specifies the attribute values that are included in the
                response. Attribute names are case-sensitive.

                For details, see
                https://docs.microsoft.com/en-us/academic-services/project-academic-knowledge/reference-entity-attributes.

        Notes
            Querying for a field that does not exist (e.g. `AuN`) results in error 500.

            Duplicate attributes are fine.
        """
        url = self._base_url + 'evaluate'
        async with self._session.get(url, params=new_filtered_dict(
            expr=expr,
            model=model,
            count=count,
            offset=offset,
            orderby=orderby,
            attributes=attributes
        ), headers=self._headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise ValueError(f'HTTP {resp.status} fetching {url}')
