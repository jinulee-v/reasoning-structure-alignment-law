/* -------------  Rules coming from the statute (only what is needed here) ------------- */

/* passenger, class and route (Europe  -> U.S.) */
passenger(susan).
flight_ticket_cost(309).                       % USD
class(basic_economy).
route(europe_to_us).

/* ------------------------  Susan's pieces of luggage ------------------------------- */
/* bag(Id, Length, Width, Height, Weight_in_lbs) */
bag(1,22,14,8,   8).     % backpack - will be her 1 free carry-on
bag(2,38,21,16, 52).
bag(3,46,24,22, 69).
bag(4,34,15,14, 65).
bag(5,35,19, 9, 67).
bag(6,38,15,10, 51).
bag(7,37,17,10, 62).
bag(8,39,23,13, 52).

/* -------------------  General utility predicates  ------------------- */
size_sum(Id,Sum) :- bag(Id,L,W,H,_), Sum is L+W+H.

/* ---------------  Carry-on (1 free) --------------- */
is_free_carry_on(Id) :-
    bag(Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9.        % fits carry-on gauge

/* ---------------  Extra (checked) bags --------------- */
checked_bag(Id) :- bag(Id,_,_,_,_), \+ is_free_carry_on(Id).

/* ---------------  Checked-bag base fee (Europe-U.S., Basic Economy) --------------- */
checked_base_fee(1,75).     % 1st bag
checked_base_fee(2,100).    % 2nd bag
checked_base_fee(N,200) :- N>=3.

/* ---------------  Oversize fee (Europe-U.S.) --------------- */
oversize_fee(Size,Fee) :-
    Size > 65  -> Fee = 150
 ;  Size > 62  -> Fee = 30
 ;  Fee = 0.

/* ---------------  Over-weight fee (Europe-U.S.) --------------- */
overweight_fee(W,Fee) :-
    ( W > 70 -> fail )                    % >70 lbs not accepted on this route
 ;  ( W > 53 -> Fee = 100 )
 ;  ( W > 50 -> Fee = 30 )
 ;  Fee = 0.

/* For each checked bag, surcharge = max(oversize, overweight) */
surcharge(Id,Fee) :-
    checked_bag(Id),
    size_sum(Id,Sz), oversize_fee(Sz,OF),
    bag(Id,_,_,_,Wt),  overweight_fee(Wt,WF),
    ( OF >= WF -> Fee = OF ; Fee = WF ).

/* -------------------  Grand-total for bags ------------------- */
all_checked_ids(Ids) :- findall(Id,checked_bag(Id),Ids).

checked_bag_cost(Total) :-
    all_checked_ids(Ids),
    checked_bag_cost(Ids,1,0,Total).

checked_bag_cost([],_,Acc,Acc).
checked_bag_cost([Id|Rest],Idx,Acc0,Total) :-
    checked_base_fee(Idx,BF),
    surcharge(Id,SF),
    Acc1 is Acc0 + BF + SF,
    Idx1 is Idx+1,
    checked_bag_cost(Rest,Idx1,Acc1,Total).

/* -------------------  Overall trip cost ------------------- */
total_cost(Total) :-
    flight_ticket_cost(Tkt),
    checked_bag_cost(Bags),
    Total is Tkt + Bags.

/* -------------------  Query ------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.