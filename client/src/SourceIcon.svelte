<script>
    export let source;
</script>

<style>
    img {
        width: 24px;
        height: 24px;
    }
</style>

<!-- TODO perhaps we should have some form of "source info" with key, name, icon -->
{#if false}
    <!-- empty for others to always be else if -->
{:else if source == 'aminer'}
    <img src="img/aminer_favicon.svg" title="Arnet Miner" alt="Arnet Miner">
{:else if source == 'academics'}
    <img src="img/academics_favicon.svg" title="Microsoft Academics" alt="Microsoft Academics">
{:else if source == 'dimensions'}
    <img src="img/dimensions_favicon.svg" title="Dimensions" alt="Dimensions">
{:else if source == 'ieeexplore'}
    <img src="img/ieeexplore_favicon.svg" title="IEEE Xplore" alt="IEEE Xplore">
{:else if source == 'researchgate'}
    <img src="img/researchgate_favicon.svg" title="ResearchGate" alt="ResearchGate">
{:else if source == 'scholar'}
    <img src="img/scholar_favicon.svg" title="Google Scholar" alt="Google Scholar">
{:else}
    <p>{source}</p>
{/if}
