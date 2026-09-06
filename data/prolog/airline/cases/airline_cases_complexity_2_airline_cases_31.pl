% ---------- Rules (statutes simplified for this case) ----------
:- use_module(library(lists)).

% passenger(Name, Class, route(Origin,Destination), ticket(Price)).
passenger(daniel, business, route(miami, buenos_aires), ticket(1108)).

% bag(PositionInCheck-inOrder, SizeSumInInches, WeightInLbs).
% (Personal item is excluded - it's free and not a checked bag.)
bag(1, 71, 99).   % 38x19x14 - oversize & >70 lbs
bag(2, 84, 91).   % 41x27x16 - oversize & >70 lbs
bag(3, 68, 55).   % 35x22x11 - oversize & 53-70 lbs
bag(4, 65, 83).   % 33x20x12 - borderline oversize & >70 lbs
bag(5, 96, 80).   % 46x26x24 - oversize & >70 lbs

% ---------- Overweight fees (U.S. <-> South America, Business) ----------
overweight_fee(W, 200) :- W > 70, !.
overweight_fee(W, 100) :- W > 53, !.
overweight_fee(W,  30) :- W > 50, !.
overweight_fee(_,   0).

% ---------- Oversize fees (U.S. <-> South America, Business) ----------
size_fee(S, 150) :- S > 65, !.       % >65-115 in
size_fee(S,  30) :- S > 62, !.       % >62-65 in
size_fee(_,   0).

% ---------- Higher of the two special-handling fees ----------
extra_fee(Size, Weight, Fee) :-
    overweight_fee(Weight, OWF),
    size_fee(Size,      OSF),
    (OWF >= OSF -> Fee = OWF ; Fee = OSF).

% ---------- Base checked-bag fee (Business, U.S. <-> S. America) ----------
% 1st & 2nd free, every bag from the 3rd onward = $200
base_checked_fee(Pos, 0)   :- Pos =< 2, !.
base_checked_fee(_,  200).

% ---------- Total fee per bag ----------
bag_total_fee(Pos, Size, Wt, Fee) :-
    extra_fee(Size, Wt, Extra),
    base_checked_fee(Pos, Base),
    Fee is Extra + Base.

% ---------- Sum of all checked-bag fees ----------
total_bag_fees(Sum) :-
    findall(F,
            (bag(P,S,W), bag_total_fee(P,S,W,F)),
            Fees),
    sum_list(Fees, Sum).

% ---------- Grand total ----------
total_cost(Total) :-
    passenger(_,_,_,ticket(Ticket)),
    total_bag_fees(BagFees),
    Total is Ticket + BagFees.

% ---------- Query ----------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.