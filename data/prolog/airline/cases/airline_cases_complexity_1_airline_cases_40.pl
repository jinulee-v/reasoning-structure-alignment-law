/* ----------  Statutory rules that apply to this case  ---------- */

/*  Base checked-bag fee for a Basic-Economy customer travelling
    to / from Japan (Austin -> Kyoto)                           */

base_bag_fee(1,75).          % 1st checked bag
base_bag_fee(2,100).         % 2nd
base_bag_fee(3,200).         % 3rd
base_bag_fee(N,200):-        % 4th and every bag thereafter
    N >= 4.

/*  Oversize fee (to / from Japan)                              */
oversize_fee(Size,0)   :- Size =< 62.            % within the limit
oversize_fee(Size,30)  :- Size  > 62, Size =< 65.
oversize_fee(Size,200) :- Size  > 65, Size =< 115.

/*  Over-weight fee (to / from Japan)                           */
overweight_fee(W,0)    :- W =< 50.               % =<50 lbs - no fee
overweight_fee(W,30)   :- W  > 50, W =< 53.      % 50-53 lbs
overweight_fee(W,100)  :- W  > 53, W =< 70.      % 53-70 lbs
overweight_fee(W,450)  :- W  > 70, W =< 100.     % 70-100 lbs

/*  For a bag that is both over-weight and over-size,
    only the HIGHER of the two fees is charged                */
extra_fee(W,Size,Fee):-
    overweight_fee(W,OWF),
    oversize_fee(Size,OSF),
    (OWF >= OSF -> Fee = OWF ; Fee = OSF).

/*  Total charge for one checked bag                           */
bag_total_fee(Index,Size,W,Total):-
    base_bag_fee(Index,Base),
    extra_fee(W,Size,Extra),
    Total is Base + Extra.

/* ----------  Facts describing Jennifer's baggage  ---------- */

/*  checked_bag(Index, Size-inches, Weight-lbs)                */
checked_bag(1,  65, 92).
checked_bag(2, 106, 52).
checked_bag(3,  65, 52).
checked_bag(4,  64, 94).
checked_bag(5,  63, 74).
checked_bag(6,  64, 64).
checked_bag(7, 110, 97).

/* ----------  Aggregations  ---------- */

sumlist([],0).
sumlist([H|T],Sum):- sumlist(T,S0), Sum is H+S0.

/*  Total of all checked-bag charges                           */
total_checked_bag_cost(Total):-
    findall(Cost,
            (checked_bag(Index,Size,W),
             bag_total_fee(Index,Size,W,Cost)),
            Costs),
    sumlist(Costs,Total).

/*  Overall cost = ticket + baggage charges                    */
total_cost(Total):-
    Ticket = 426,                          % given in the case
    total_checked_bag_cost(Bags),
    Total is Ticket + Bags.

/* ----------  Query to produce the answer  ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.