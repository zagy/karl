/*jslint undef: true, newcap: true, nomen: false, white: true, regexp: true *//*jslint plusplus: false, bitwise: true, maxerr: 50, maxlen: 110, indent: 4 *//*jslint sub: true *//*globals window navigator document console *//*globals setTimeout clearTimeout setInterval *//*globals jQuery DD_roundies alert confirm */(function(a){var b=function(){window.console&&console.log&&console.log(Array.prototype.slice.call(arguments))};a.widget("karl.karlcalendarbuttons",{options:{ddRoundies:!1,ie8OnePixelCompensate:!0},_create:function(){var b=this;this.element.append('<span class="karl-calendar-buttonset-term"><input type="radio" name="karl-calendar-buttonset-term" id="karl-calendar-button-day" class="karl-calendar-button-day"></input><label for="karl-calendar-button-day">Day</label><input type="radio" name="karl-calendar-buttonset-term" id="karl-calendar-button-week" class="karl-calendar-button-week"></input><label for="karl-calendar-button-week">Week</label><input type="radio" name="karl-calendar-buttonset-term" id="karl-calendar-button-month" class="karl-calendar-button-month"></input><label for="karl-calendar-button-month">Month</label></span><span class="karl-calendar-buttonset-viewtype"><input type="radio" name="karl-calendar-buttonset-viewtype" id="karl-calendar-button-calendar" class="karl-calendar-button-calendar"></input><label for="karl-calendar-button-calendar">Calendar</label><input type="radio" name="karl-calendar-buttonset-viewtype" id="karl-calendar-button-list" class="karl-calendar-button-list"></input><label for="karl-calendar-button-list">List</label></span><button class="karl-calendar-button-today">Today</button><span class="karl-calendar-buttonset-navigate"><input type="radio" name="karl-calendar-buttonset-navigate" id="karl-calendar-button-prev" class="karl-calendar-button-prev"></input><label for="karl-calendar-button-prev" class="karl-calendar-label-prev">&nbsp;</label><input type="radio" name="karl-calendar-buttonset-navigate" id="karl-calendar-button-next" class="karl-calendar-button-next"></input><label for="karl-calendar-button-next" class="karl-calendar-label-next">&nbsp;</label></span><select class="karl-calendar-dropdown-year"></select><select class="karl-calendar-dropdown-month"><option value="1">Jan</option><option value="2">Feb</option><option value="3">Mar</option><option value="4">Apr</option><option value="5">May</option><option value="6">Jun</option><option value="7">Jul</option><option value="8">Aug</option><option value="9">Sep</option><option value="10">Oct</option><option value="11">Nov</option><option value="12">Dec</option></select><select class="karl-calendar-dropdown-day"></select>');this.el_b_today=this.element.find(".karl-calendar-button-today");this.el_bs_navigate=this.element.find(".karl-calendar-buttonset-navigate");this.el_b_prev=this.element.find(".karl-calendar-button-prev");this.el_b_next=this.element.find(".karl-calendar-button-next");this.el_dd_year=this.element.find(".karl-calendar-dropdown-year");this.el_dd_month=this.element.find(".karl-calendar-dropdown-month");this.el_dd_day=this.element.find(".karl-calendar-dropdown-day");this.el_bs_viewtype=this.element.find(".karl-calendar-buttonset-viewtype");this.el_b_calendar=this.element.find(".karl-calendar-button-calendar");this.el_b_list=this.element.find(".karl-calendar-button-list");this.el_bs_term=this.element.find(".karl-calendar-buttonset-term");this.el_b_day=this.element.find(".karl-calendar-button-day");this.el_b_week=this.element.find(".karl-calendar-button-week");this.el_b_month=this.element.find(".karl-calendar-button-month");this.el_b_today.button({});this.el_b_today.click(function(a){var c=new Date,d=b.options.selection||{},e=c.getFullYear(),f=c.getMonth()+1,g=c.getDate();if(d.year!=e||d.month!=f||d.day!=g){b.options.selection.year=e;b.options.selection.month=f;b.options.selection.day=g;return b._change(a)}});this.el_bs_navigate.buttonset({});this.el_b_prev.button("option","icons",{primary:"ui-icon-triangle-1-w"}).change(function(a){return b._navigate(a,-1)});this.el_b_next.button("option","icons",{primary:"ui-icon-triangle-1-e"}).change(function(a){return b._navigate(a,1)});var c;for(c=2e3;c<2025;c++)this.el_dd_year.append('<option value="'+c+'">'+c+"</option>");this.el_dd_year.change(function(c){var d=Number(a(this).val());if(d>0&&b.options.selection.year!=d){b.options.selection.year=d;return b._change(c)}});this.el_dd_month.change(function(c){var d=Number(a(this).val());if(d>0&&b.options.selection.month!=d){b.options.selection.month=d;return b._change(c)}});this.el_dd_day.change(function(c){var d=Number(a(this).val());if(d>0&&b.options.selection.day!=d){b.options.selection.day=d;return b._change(c)}});this.el_bs_viewtype.buttonset({});this.el_b_calendar.change(function(a){if(b.options.selection.viewtype!="calendar"){b.options.selection.viewtype="calendar";return b._change(a)}});this.el_b_list.change(function(a){if(b.options.selection.viewtype!="list"){b.options.selection.viewtype="list";return b._change(a)}});this.el_bs_term.buttonset({});this.el_b_day.change(function(a){if(b.options.selection.term!="day"){b.options.selection.term="day";return b._change(a)}});this.el_b_week.change(function(a){if(b.options.selection.term!="week"){b.options.selection.term="week";return b._change(a)}});this.el_b_month.change(function(a){if(b.options.selection.term!="month"){b.options.selection.term="month";return b._change(a)}});this._updateSelection();this.element.find("a.ui-selectmenu").each(function(){a(this).css("margin-top","-4px")});if(a.browser.msie&&a.browser.version<=7){this.element.find("a.ui-selectmenu").each(function(){a(this).css("top","-2px")});this.element.find(".karl-calendar-label-prev, .karl-calendar-label-next").each(function(){a(this).css("top","-2px").height(a(this).height()+1)})}if(this.options.ddRoundies){if(!DD_roundies)throw new Error("DD_roundies must be present, or ddRoundies=false option must be specified.");DD_roundies.addRule(".cal-toolbar .ui-corner-left","4px 0 0 4px");DD_roundies.addRule(".cal-toolbar .ui-corner-right","0 4px 4px 0");DD_roundies.addRule(".cal-toolbar .ui-corner-all","4px 4px 4px 4px")}this.options.ddRoundies&&this.options.ie8OnePixelCompensate&&a.browser.msie&&a.browser.version==8&&this.element.find(".ui-corner-left, .ui-corner-right, .ui-corner-all").each(function(){a(this).css("top","1px").css("left","1px").children().each(function(){var b=a(this);b.css("position")=="static"&&b.css("position","relative").css("top",""+(this.offsetTop-2)+"px").css("left",""+(this.offsetLeft-2)+"px")})})},disable:function(a){this.el_b_today.button("option","disabled",!0);this.el_bs_navigate.buttonset("option","disabled",!0);this.el_dd_year.attr("disabled",!0);this.el_dd_month.attr("disabled",!0);this.el_dd_day.attr("disabled",!0);this.el_bs_viewtype.buttonset("option","disabled",!0);this.el_bs_term.buttonset("option","disabled",!0)},_navigate:function(a,b){var c=this.options.selection||{},d=c.term,e=864e5,f,g;if(d=="month"){this.options.selection.month+=b;if(this.options.selection.month===0){this.options.selection.month=12;this.options.selection.year-=1}else if(this.options.selection.month==13){this.options.selection.month=1;this.options.selection.year+=1}}else if(d=="week"){f=new Date(c.year,c.month-1,c.day);g=new Date(f.getTime()+b*7*e);this.options.selection.year=g.getFullYear();this.options.selection.month=g.getMonth()+1;this.options.selection.day=g.getDate()}else if(d=="day"){f=new Date(c.year,c.month-1,c.day);g=new Date(f.getTime()+b*e);this.options.selection.year=g.getFullYear();this.options.selection.month=g.getMonth()+1;this.options.selection.day=g.getDate()}return this._change(a)},_change:function(a){this._updateSelection();this._trigger("change",a,this.options.selection)},_setOption:function(b,c){var d=b=="selection"&&this._isSelectionChanged(this.options.selection,c);a.Widget.prototype._setOption.call(this,b,c);d&&this._updateSelection()},_isSelectionChanged:function(a,b){return!a&&!b?!1:!a||!b?!0:a.viewtype!=b.viewtype||a.term!=b.term||a.year!=b.year||a.month!=b.month||a.day!=b.day},_updateDays:function(){var a=this,b=this.options.selection||{};this.el_dd_day.empty();var c=b.month,d;if(c==2){var e=b.year;e%4===0&&(e==2e3||e%100>0)?d=29:d=28}else c==4||c==6||c==9||c==11?d=30:d=31;var f;for(f=1;f<=d;f++)this.el_dd_day.append('<option value="'+f+'">'+f+"</option>")},_updateSelection:function(){var a=this.options.selection||{};this._updateDays();var b=new Date,c=b.getFullYear(),d=b.getMonth()+1,e=b.getDate(),f=a.year==c&&a.month==d&&a.day==e;this.el_b_today.button("option","disabled",f);this.el_dd_year.val(""+a.year);this.el_dd_month.val(""+a.month);this.el_dd_day.val(""+a.day);var g={calendar:this.el_b_calendar,list:this.el_b_list}[a.viewtype];g&&g.attr("checked","checked");this.el_bs_viewtype.buttonset("refresh");var h={day:this.el_b_day,week:this.el_b_week,month:this.el_b_month}[a.term];h&&h.attr("checked","checked");this.el_bs_term.buttonset("refresh")},destroy:function(){this.el_b_today.button("destroy");this.el_bs_navigate.buttonset("destroy");this.el_bs_viewtype.buttonset("destroy");this.el_bs_term.buttonset("destroy");a.Widget.prototype.destroy.call(this)}})})(jQuery);