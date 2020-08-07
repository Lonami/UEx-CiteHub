<script>
    import ProfileSettings from './ProfileSettings.svelte';
    import Publications from './Publications.svelte';
    import Login from './Login.svelte';
    import Logout from './Logout.svelte';
    import Navigation from './Navigation.svelte';
    import Metrics from './Metrics.svelte';
</script>

<Navigation/>

{#if window.location.pathname === '/'}
    <p>There is nothing here. Check one of the other pages in the navigation above.</p>
{:else if window.location.pathname === '/register'}
    <Login register={true}/>
{:else if window.location.pathname === '/login'}
    <Login register={false}/>
{:else if window.location.pathname === '/metrics'}
    <Metrics/>
{:else if window.location.pathname === '/publications'}
    <Publications/>
{:else if window.location.pathname === '/settings'}
    <ProfileSettings/>
{:else if window.location.pathname === '/logout'}
    <Logout/>
{:else}
    <h2>404</h2>
    <p>No such page exists at {window.location.pathname}. Try one of the pages above.</p>
{/if}
