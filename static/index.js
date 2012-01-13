/* Hackathon jQuery power! */
window.fbAsyncInit = function() {
  FB.init({
    appId      : '280095635370290',
    channelUrl : '//friend.herokuapp.com/channel.html',
    cookie     : true,
    oauth      : true,
  });

  $('#create_list').submit(function(e) {
    e.preventDefault();

    var status_msg = $('#status_msg');
    var form = $(this);
    var name = form.find('input[name="list_name"]');
    var countries = form.find('input[name="countries"]');
    var languages = form.find('input[name="languages"]');
    var single = form.find('input[name="single"]');
    var age_min = form.find('input[name="age_min"]');
    var age_max = form.find('input[name="age_max"]');

    var perms = ['manage_friendlists', 'read_friendlists'];
    if(languages.val()) perms.push('friends_likes');
    if(countries.val()) perms = perms.concat(['friends_location',
      'friends_hometown']);
      if(single.val()) perms.push('friends_relationships');
      if(age_min.val() || age_max.val()) perms.push('friends_birthday');

      if(name.val()) {
        form.slideUp('slow');
        status_msg.fadeOut('slow', function() {
          status_msg.text('Getting authorization ..').fadeIn('slow');
        });

        FB.login(function(response) {
          if (response.authResponse) {
            status_msg.fadeOut('slow', function() {
              status_msg.text('Loading ..').fadeIn('slow');
            });

            $.post('./create', form.serialize()).success(function(data) {
              var list_id = data['list_id'];
              status_msg.fadeOut('slow', function() {
                status_msg
                .html('Success! Go to <a href="https://facebook.com/lists/'
                +list_id+'">Facebook</a> and enjoy.')
                .fadeIn('slow');
              });
              console.log('Holy shit, it worked!');
            }).fail(function() {
              status_msg.fadeOut('slow', function() {
                status_msg
                .text('Failure! Try again?')
                .fadeIn('slow', function() {
                  form.slideDown('slow');
                });
              });
              console.log('Unholy shit, it did not work!');
            }).always(function() {
              // pass
            });
          } else { // user did not authorize
            status_msg.fadeOut('slow', function() {
              status_msg.text('No permissions, no fun. Sorry.').fadeIn('slow');
            });
            form.slideDown('slow');
          }
        }, {scope: perms.join(',')}); // only request required permissions
      } else {
        name.val('Can I please have a name?');
      }
      return false;
  });
};

// Load Facebook SDK Asynchronously
(function(d){
  var js, id = 'facebook-jssdk'; if (d.getElementById(id)) {return;}
  js = d.createElement('script'); js.id = id; js.async = true;
  js.src = "//connect.facebook.net/en_US/all.js";
  d.getElementsByTagName('head')[0].appendChild(js);
}(document));
