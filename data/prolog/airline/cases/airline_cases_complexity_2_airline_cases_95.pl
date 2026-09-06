/************************************************************************
  Statutory rules (only the parts that matter for this case)
*************************************************************************/

% flight region and service class for the itinerary
region(within_us).
service_class(main_cabin).

% cost of the ticket itself
ticket_cost(76).

/* ---------- size / weight surcharges ---------- */

oversize_fee(Size, 0)              :- Size =< 62, !.
oversize_fee(Size, 30)             :- Size  > 62, Size =< 65, !.
oversize_fee(Size, 200)            :- Size  > 65, Size =< 115.

overweight_fee(Weight, 0)          :- Weight =< 50, !.
overweight_fee(Weight, 30)         :- Weight  > 50, Weight =< 53, !.
overweight_fee(Weight, 100)        :- Weight  > 53, Weight =< 70, !.
overweight_fee(Weight, 200)        :- Weight  > 70, Weight =< 100.

/* ---------- base checked-bag fee (within U.S., Main Cabin) ---------- */

checked_bag_base_fee(Index, 40)    :- Index =:= 1, !.   % 1st checked bag
checked_bag_base_fee(Index, 45)    :- Index =:= 2, !.   % 2nd checked bag
checked_bag_base_fee(Index, 150)   :- Index =:= 3, !.   % 3rd checked bag
checked_bag_base_fee(_, 200).                          % 4th bag +

/************************************************************************
  Facts for Daniel's pieces of baggage
  bag(Id, Length, Width, Height, Weight).
*************************************************************************/

% Bag 1 is carried on (free) so we do not list it here.

bag(2, 36, 16, 12, 59).
bag(3, 37, 16, 12, 62).
bag(4, 47, 28, 21, 51).
bag(5, 51, 29, 23, 51).
bag(6, 43, 20, 15, 68).
bag(7, 38, 16, 14, 65).
bag(8, 38, 21, 11, 53).
bag(9, 47, 32, 24, 53).
bag(10, 37, 16, 10, 99).
bag(11, 45, 24, 16, 65).

/* We state the order in which the checked bags are presented */
bag_order(2,1).
bag_order(3,2).
bag_order(4,3).
bag_order(5,4).
bag_order(6,5).
bag_order(7,6).
bag_order(8,7).
bag_order(9,8).
bag_order(10,9).
bag_order(11,10).

/************************************************************************
  Derived predicates
*************************************************************************/

% linear size of a bag
linear_size(Id, S) :-
    bag(Id, L, W, H, _),
    S is L + W + H.

% surcharge for a bag (the higher of overweight / oversize)
bag_surcharge(Id, Surcharge) :-
    bag(Id, _, _, _, Weight),
    linear_size(Id, Size),
    oversize_fee(Size, OSizeFee),
    overweight_fee(Weight, OWeightFee),
    Surcharge is max(OSizeFee, OWeightFee).

% total cost for one checked bag = base fee (by position) + surcharge
bag_total_cost(Id, Cost) :-
    bag_order(Id, Index),
    checked_bag_base_fee(Index, Base),
    bag_surcharge(Id, Surcharge),
    Cost is Base + Surcharge.

% sum of all checked-bag costs
total_checked_bag_cost(Total) :-
    findall(C, bag_total_cost(_, C), Costs),
    sum_list(Costs, Total).

% grand total: ticket + checked bags  (no extra "special needs" costs here)
total_cost(Total) :-
    ticket_cost(T),
    total_checked_bag_cost(Bags),
    Total is T + Bags.

/************************************************************************
  Query - prints the answer required by the problem statement
*************************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.