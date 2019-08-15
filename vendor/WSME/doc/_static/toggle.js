/*global $,document*/
$(document).ready(function () {
    "use strict";
    $("dl.toggle > dt").click(
        function (event) {
            $(this).next().toggle(250);
        }
    );
});
