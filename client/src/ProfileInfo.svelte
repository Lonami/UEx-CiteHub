<script>
    // Dummy value for now
    let profile = {
        name: 'Name Last-Name',
        affiliation: 'Affiliation Name (AN), Country',
        email: 'domain.tld'
    };
</script>

<style>
    .profile-info {
        display: flex;
        line-height: 0.4;
        margin-bottom: 16px;
    }

    .profile-info img {
        width: 128px;
        height: 128px;
        border-radius: 50%;
        margin-right: 16px;
    }

    .name {
        font-size: x-large;
    }
</style>

<div class="profile-info">
    <img src="img/generic_avatar.svg" alt={profile.name}>
    <div>
        <p class="name">{profile.name}</p>
        <p class="affiliation">{profile.affiliation}</p>
        <p class="email">Verified email at {profile.email}</p>
    </div>
</div>
