<script>
    export let source;
</script>

<style>
    img {
        width: 24px;
        height: 24px;
    }
</style>

{#if source == 'google-scholar'}
    <img src="img/scholar_favicon.svg" title="Google Scholar" alt="Google Scholar">
{:else if source == 'scopus'}
    <img src="img/scopus_favicon.svg" title="Scopus" alt="Scopus">
{:else if source == 'ms-academics'}
    <img src="img/academics_favicon.svg" title="Microsoft Academics" alt="Microsoft Academics">
{:else}
    <p>{source}</p>
{/if}
