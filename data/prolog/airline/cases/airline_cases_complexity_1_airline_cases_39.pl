/* ----------  Statutory rules (extracted and simplified) ---------- */

/* passenger, route and ticket facts */
passenger(michael).
class(michael, first_class).
route(michael, us_to_mexico).
ticket_price(michael, 165).

/* bag( Id, L, W, H, WeightLbs ).                                   */
bag(michael, 1, 21, 12,  6,  6).
bag(michael, 2, 33, 18, 12, 76).
bag(michael, 3, 34, 19, 13, 61).
bag(michael, 4, 33, 16, 14, 79).
bag(michael, 5, 38, 14, 13, 72).
bag(michael, 6, 37, 16, 15, 71).

/* ------------------ carry-on / checked split -------------------- */

/* carry-on: fits 22*14*9 inches                                    */
carry_on(P,Id) :-
    bag(P,Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

checked_bag(P,Id) :-
    bag(P,Id,_,_,_,_),
    \+ carry_on(P,Id).

/* ------------------ base checked-bag fee ------------------------ */

% First-class, US <-> Mexico / Caribbean / C.A.
% 1st-3rd bag free, 4th+ = $200 each
base_fee(P,N,0) :- class(P,first_class), route(P,us_to_mexico), N =< 3.
base_fee(P,N,200) :- class(P,first_class), route(P,us_to_mexico), N >= 4.

/* ------------------ overweight fee ------------------------------ */

overweight_fee(_,W,0)      :- W =< 50.
overweight_fee(_,W,30)     :- W > 50 , W =< 53.
overweight_fee(us_to_mexico,W,100) :- W > 53 , W =< 70.
overweight_fee(us_to_mexico,W,200) :- W > 70 , W =< 100.

/* ------------------ oversize fee -------------------------------- */

oversize_fee(_,S,0)    :- S =< 62.
oversize_fee(_,S,30)   :- S > 62 , S =< 65.
oversize_fee(_,S,200)  :- S > 65 , S =< 115.

/* ------------------ per-bag total extra (over-/oversize) -------- */

extra_fee(P,Id,Fee) :-
    route(P,Rt),
    bag(P,Id,L,W,H,Weight),
    S is L+W+H,                        % size in inches
    overweight_fee(Rt,Weight,OW),
    oversize_fee(Rt,S,OS),
    Fee is max(OW,OS).

/* ------------------ aggregate all bag fees ---------------------- */

bag_total_fee(P,Id,N,Total) :-
    base_fee(P,N,Base),
    extra_fee(P,Id,Extra),
    Total is Base + Extra.

/* Produce ordered list of checked bags to assign 1st,2nd...        */
checked_bags_ordered(P,List) :-
    findall(Id, checked_bag(P,Id), Raw),
    sort(Raw,List).                     % ascending id order

/* Sum of all luggage charges                                       */
luggage_cost(P,Sum) :-
    checked_bags_ordered(P,List),
    findall(F,
        (
          nth1(N,List,Id),
          bag_total_fee(P,Id,N,F)
        ),
        Fees),
    sum_list(Fees,Sum).

/* ------------------ grand total --------------------------------- */

total_cost(Total) :-
    passenger(P),
    ticket_price(P,Ticket),
    luggage_cost(P,Lug),
    Total is Ticket + Lug.

/* ------------------ query & print ------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.