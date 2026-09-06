% ---------- Rules that encode the statutory provisions
% Regions (only the one we need here)
region(within_us).

% ---------------- Oversize fees (domestic)
% Size is length+width+height (inches)
oversize_fee(Region, Size, 0) :-
    Size =< 62, !.                      % at or below the free size
oversize_fee(within_us, Size, 30) :-    % 62-65 in
    Size  > 62, Size =< 65, !.
oversize_fee(within_us, Size, 200) :-   % 65-115 in
    Size  > 65, Size =< 115, !.
oversize_fee(_, _, 0).                  % otherwise (not applicable here)

% ---------------- Over-weight fees (domestic)
overweight_fee(_, W, 0) :- W =< 50, !.              % up to 50 lb free
overweight_fee(within_us, W, 30) :-                 % 50-53 lb
    W  > 50, W =< 53, !.
overweight_fee(within_us, W, 100) :-                % 53-70 lb
    W  > 53, W =< 70, !.
overweight_fee(within_us, W, 200) :-                % 70-100 lb
    W  > 70, W =< 100, !.

% ---------------- Base checked-bag fee for First Class, domestic
% Seq = 1,2 free; 3rd = $150; 4th+ = $200
base_checked_fee(first, within_us, Seq, 0)   :- Seq =< 2, !.
base_checked_fee(first, within_us, 3, 150)   :- !.
base_checked_fee(first, within_us, Seq, 200) :- Seq >= 4.

% ---------------- Surcharge (higher of oversize / overweight)
surcharge(Region, Size, Weight, Fee) :-
    oversize_fee(Region, Size, F1),
    overweight_fee(Region, Weight, F2),
    Fee is max(F1, F2).

% ---------------- A bag's total charge
bag_charge(Class, Region, Seq, Size, Weight, Charge) :-
    base_checked_fee(Class, Region, Seq, Base),
    surcharge(Region, Size, Weight, Surcharge),
    Charge is Base + Surcharge.

% ---------- Facts describing Robert's situation
passenger(robert).
class(robert, first).
flight_region(robert, within_us).
ticket_price(robert, 61).

% Each bag: id, L, W, H (in), Weight (lb)
bag(b1, 22, 14,  7, 12).   % intended carry-on
bag(b2, 50, 32, 25, 52).
bag(b3, 45, 27, 23, 53).
bag(b4, 36, 20,  9, 52).
bag(b5, 47, 31, 22, 52).

% ---------- Helper predicates
size(Id, S) :- bag(Id,L,W,H,_), S is L+W+H.
weight(Id,W) :- bag(Id,_,_,_,W).

% A bag is a free carry-on if it fits 22*14*9
carry_on(Id) :-
    bag(Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

% Collect checked bags in their sequence order
checked_sequence(List) :-
    findall(Id, (bag(Id,_,_,_,_), \+ carry_on(Id)), Raw),
    sort(Raw, List).   % keeps original order given by identifiers

% Compute total bag fees for Robert
total_bag_fees(Total) :-
    class(robert, Class),
    flight_region(robert, Region),
    checked_sequence(Bags),
    compute_fees(Bags, 1, Class, Region, 0, Total).

compute_fees([], _, _, _, Acc, Acc).
compute_fees([Id|Rest], Seq, Class, Region, Acc0, Total) :-
    size(Id, Size),
    weight(Id, Wgt),
    bag_charge(Class, Region, Seq, Size, Wgt, Fee),
    Acc1 is Acc0 + Fee,
    Seq1 is Seq + 1,
    compute_fees(Rest, Seq1, Class, Region, Acc1, Total).

% Overall total (ticket + bags)
total_cost(Total) :-
    ticket_price(robert, Ticket),
    total_bag_fees(BagFees),
    Total is Ticket + BagFees.

% ----------- Query to print the result
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.