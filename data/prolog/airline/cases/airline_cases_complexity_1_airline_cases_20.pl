/* ----------  Facts from the case  ---------- */

ticket_price(259).                 % Ticket cost in U.S. dollars
class(first).                      % Linda is travelling First Class
route(domestic).                   % New-York -> Philadelphia (within U.S.)

% checked_item(ID,Length,Width,Height,Weight).
checked_item(1,39,28,15,81).       % luggage box
checked_item(2,37,17,14,56).       % luggage box
checked_item(3,51,30,26,68).       % backpack
checked_item(4,38,20,10,53).       % luggage box
checked_item(5,44,22,20,53).       % luggage box
checked_item(6,35,17,13,98).       % backpack
checked_item(7,36,17,11,64).       % backpack

num_checked_bags(N) :- aggregate_all(count, checked_item(_,_,_,_,_), N).

/* ----------  Bag-number fees (First Class, domestic) ---------- */

bag_number_fee(Index,0)   :- Index =< 2.               % 1st & 2nd bags free
bag_number_fee(3,150).
bag_number_fee(Index,200) :- Index >= 4.

/* ----------  Oversize fees (domestic)  ---------- */

oversize_fee(Size,0)                       :- Size =< 62.
oversize_fee(Size,30)                      :- Size  > 62, Size =< 65.
oversize_fee(Size,200)                     :- Size  > 65, Size =< 115.

/* ----------  Over-weight fees (domestic) ---------- */
/* For First-Class complimentary bags (1st & 2nd) the weight allowance is 70 lb   */
/* For all paid bags the standard 50-lb limit applies                             */

overweight_fee(Weight,free,200) :- Weight >  70, Weight =< 100.
overweight_fee(Weight,free,0)   :- Weight =< 70.

overweight_fee(Weight,paid,200) :- Weight >  70, Weight =< 100.
overweight_fee(Weight,paid,100) :- Weight >  50, Weight =< 70.
overweight_fee(Weight,paid,0)   :- Weight =< 50.

/* ----------  Utility predicates ---------- */

size(L,W,H, S) :- S is L+W+H.

max(X,Y,X) :- X >= Y.
max(X,Y,Y) :- Y >  X.

/* charge_for_bag(ID,Status,Charge)
      Status = free | paid   (with respect to the 1st / 2nd free allowance)
      Charge  = max(oversize, overweight) for that bag                       */

charge_for_bag(ID,Status,Charge) :-
    checked_item(ID,L,W,H,Weight),
    size(L,W,H,Size),
    oversize_fee(Size, OFee),
    overweight_fee(Weight,Status, WFee),
    max(OFee,WFee,Charge).

/* ----------  Choose which 2 bags are "free" so that charges are minimal ------- */

% pick/3  - combination helper  (pick N elements from a list)
pick(0,_,[]) :- !.
pick(N,[X|Xs],[X|Ys]) :- N>0, N1 is N-1, pick(N1,Xs,Ys).
pick(N,[_|Xs],Ys)     :- N>0, pick(N,Xs,Ys).

% list of all bag IDs
bag_ids(IDs) :- findall(ID, checked_item(ID,_,_,_,_), IDs).

% total oversize/over-weight cost for a specific choice of FreeIDs
combo_cost(FreeIDs,Cost) :-
    bag_ids(AllIDs),
    % charges for the 2 complimentary bags
    findall(C, (member(ID,FreeIDs), charge_for_bag(ID,free,C)),  FreeCs),
    % charges for the remaining paid bags
    findall(C, (member(ID,AllIDs), \+ member(ID,FreeIDs),
                charge_for_bag(ID,paid,C)),                     PaidCs),
    sum_list(FreeCs,FreeSum),
    sum_list(PaidCs,PaidSum),
    Cost is FreeSum + PaidSum.

% find the minimum possible over/oversize cost
min_extra_cost(MinCost) :-
    bag_ids(IDs),
    setof(Cost, FreeIDs^(
            pick(2,IDs,FreeIDs),
            combo_cost(FreeIDs,Cost)
          ), [MinCost|_]).

/* ----------  Bag-number fee for ALL checked bags (7 of them) ------------------ */

bag_number_total(Total) :-
    num_checked_bags(N),
    findall(F, (between(1,N,I), bag_number_fee(I,F)), Fs),
    sum_list(Fs,Total).

/* ----------  Grand total ------------------------------------------------------ */

total_cost(Total) :-
    min_extra_cost(ExtraFees),
    bag_number_total(BagCountFees),
    ticket_price(Tix),
    Total is Tix + BagCountFees + ExtraFees.

/* ----------  Query to print the answer --------------------------------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.