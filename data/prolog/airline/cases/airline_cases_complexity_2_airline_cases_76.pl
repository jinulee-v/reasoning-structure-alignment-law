/* -------------  Statutory rules needed for this case ------------- */

/* flight data */
ticket_price(349).                 % USD
cabin_class(basic_economy).        % Emily's fare class
route(india_to_usa).               % Mumbai (India) --> San Francisco (U.S.)

/* ----------  Carry-on allowance (1 bag is free)  -----------------*/
carryon_id(1).                     % item #1 is her carry-on (free)

/* ----------  Checked-bag base fees for Basic-Economy               */
/* India <-> U.S. - 1st:$75, 2nd:$100, 3rd+:$200                       */
bag_base_fee(1,75).
bag_base_fee(2,100).
bag_base_fee(N,200):- N>=3.

/* ----------  Over-WEIGHT fees (India <-> U.S.) --------------------- */
overweight_fee(W,0 ) :- W =< 50.
overweight_fee(W,30) :- W > 50 , W =< 53.
overweight_fee(W,100):- W > 53 , W =< 70.
overweight_fee(W,450):- W > 70 , W =< 100.

/* ----------  Over-SIZE fees (India <-> U.S.) ----------------------- */
oversize_fee(D,0 ) :- D =< 62.
oversize_fee(D,30) :- D > 62 , D =< 65.
oversize_fee(D,200):- D > 65 , D =< 115.

/* ----------  Highest of over-size / over-weight ------------------ */
extra_fee(W,D,Fee):-
    overweight_fee(W,OW),
    oversize_fee(D,OS),
    (OW>=OS -> Fee=OW ; Fee=OS).

/* ----------  Passenger's bags  ----------------------------------- */
% bag(Id,Length,Width,Height,Weight)
bag(1,21,11, 9,  8).   % carry-on
bag(2,36,18,10, 95).
bag(3,37,13,14, 84).
bag(4,39,21,12, 61).
bag(5,39,25,13, 53).
bag(6,50,30,27, 72).
bag(7,37,17,11, 88).
bag(8,38,17,17, 52).
bag(9,38,20,18, 52).
bag(10,48,33,26,90).
bag(11,33,19,11,87).

/* ----------  Helper predicates ----------------------------------- */
checked_bag(Id):- bag(Id,_,_,_,_), \+ carryon_id(Id).

bag_dimension(Id,Dim):-
    bag(Id,L,W,H,_),
    Dim is L+W+H.

/* cost of one checked bag given its check-in order ---------------- */
one_bag_cost(Order,Id,Cost):-
    bag(Id,_,_,_,Wt),
    bag_dimension(Id,Dim),
    bag_base_fee(Order,Base),
    extra_fee(Wt,Dim,Extra),
    Cost is Base+Extra.

/* list processing -------------------------------------------------- */
bag_costs([],_,[]).
bag_costs([Id|Rest],Order,[Cost|Cs]):-
    one_bag_cost(Order,Id,Cost),
    Next is Order+1,
    bag_costs(Rest,Next,Cs).

checked_bags_ordered(List):-
    findall(Id,checked_bag(Id),Unsorted),
    sort(Unsorted,List).          % ascending id order (2-11)

/* total of all checked-bag fees ----------------------------------- */
total_checked_bag_fees(Total):-
    checked_bags_ordered(Ids),
    bag_costs(Ids,1,Costs),
    sum_list(Costs,Total).

/* ---------------  Grand total Emily must pay  -------------------- */
total_cost(Total):-
    total_checked_bag_fees(Bags),
    ticket_price(Tkt),
    Total is Bags + Tkt.

/* --------------------  Query / output  --------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.